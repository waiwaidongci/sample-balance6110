"""Bootstrap uncertainty for the weighted mean, re-calibrating each resample."""
import hashlib,json,math,random
from statistics import mean,median
from fastapi import HTTPException
from sqlalchemy import select
from src.models import BootstrapAnalysis
from src.utils.serializers import serialize
from src.utils.audit import record
from src.config.queue import queue,BOOTSTRAP_QUEUE
from .run_service import get_run
from .raking_algorithm import recalibrate

QUEUE=BOOTSTRAP_QUEUE
UNIT_FIELDS=('code','zone','age_band','mode','trip_minutes','base_weight')
LEVEL=.95

def _public(row,full=False):
    data=serialize(row)
    if not full and data.get('result'):
        data['result']={key:value for key,value in data['result'].items() if key!='replicates_detail'}
    return data

def list_analyses(db,run_id):
    get_run(db,run_id)
    return [_public(x) for x in db.scalars(select(BootstrapAnalysis).where(BootstrapAnalysis.run_id==run_id).order_by(BootstrapAnalysis.id.desc()))]

def get_analysis(db,analysis_id):
    row=db.get(BootstrapAnalysis,analysis_id)
    if not row:raise HTTPException(404,'重抽样分析不存在')
    return row

def create(db,run_id,data,user):
    run=get_run(db,run_id)
    if run.status!='completed' or not run.result:raise HTTPException(409,'仅可对已完成且保留结果的校准运行重抽样')
    if not run.result.get('assignments') or not run.result.get('diagnostics'):raise HTTPException(409,'该运行未保留样本与目标快照，无法重抽样')
    row=BootstrapAnalysis(run_id=run_id,replicates=data.replicates,seed=data.seed,created_by=user.id)
    db.add(row);db.flush();record(db,user,'create_bootstrap',row.id);db.commit()
    try:queue.rpush(QUEUE,str(row.id))
    except Exception:row.status='failed';row.error='队列不可用，请稍后重新发起重抽样';db.commit()
    return serialize(row)

def _quantile(sorted_values,p):
    if not sorted_values:return None
    pos=(len(sorted_values)-1)*p;low=math.floor(pos);high=math.ceil(pos)
    return sorted_values[low]+(sorted_values[high]-sorted_values[low])*(pos-low)

def _resample(units,seed,replicates):
    rng=random.Random(seed);n=len(units)
    draws=[]
    for _ in range(replicates):
        counts={}
        for _ in range(n):
            index=rng.randrange(n);counts[index]=counts.get(index,0)+1
        draws.append(counts)
    return draws

def _replicate_units(units,counts):
    replicated=[]
    for index,unit in enumerate(units):
        copies=counts.get(index,0)
        for copy in range(copies):
            row={key:unit[key] for key in UNIT_FIELDS}
            # The code is only an identifier; a copy suffix keeps the raking uniqueness check meaningful.
            row['code']=f"{unit['code']}~{copy+1}"
            replicated.append(row)
    return replicated

def summarize(replicates,means,failures,meta):
    valid=len(means)
    required=math.ceil(replicates*.9)
    summary=dict(meta)
    summary.update({
        'replicates':replicates,
        'valid_count':valid,
        'excluded_count':replicates-valid,
        'required_for_interval':required,
        'interval':None,
        'interval_level':LEVEL,
        'bootstrap_mean':None,
        'bootstrap_median':None,
        'bootstrap_std_error':None,
        'failure_reasons':[{'reason':reason,'count':count} for reason,count in sorted(failures.items(),key=lambda x:(-x[1],x[0]))],
    })
    if valid*10>=replicates*9:
        ordered=sorted(means)
        centre=mean(means)
        summary['interval']={'low':_quantile(ordered,(1-LEVEL)/2),'high':_quantile(ordered,1-(1-LEVEL)/2)}
        summary['bootstrap_mean']=centre
        summary['bootstrap_median']=median(means)
        summary['bootstrap_std_error']=((sum((x-centre)**2 for x in means)/(valid-1))**.5) if valid>1 else None
    return summary

def compute(db,analysis_id):
    analysis=get_analysis(db,analysis_id)
    if analysis.status in ('completed','failed'):return
    analysis.status='running';analysis.result={'progress_done':0,'progress_total':analysis.replicates};db.commit()
    try:
        run=get_run(db,analysis.run_id)
        if run.status!='completed' or not run.result:raise ValueError('原校准结果不可用')
        units=[{key:row[key] for key in UNIT_FIELDS} for row in run.result['assignments']]
        # The run snapshot keeps the target each category was fitted to; later target edits never rewrite it.
        targets=[{'dimension':d['dimension'],'category':d['category'],'population':d['target']} for d in run.result['diagnostics']]
        tolerance,max_iterations,cap_ratio=run.tolerance,run.max_iterations,run.cap_ratio
    except Exception as exc:
        analysis.status='failed';analysis.error=f'读取原校准失败：{str(exc)[:400]}';db.commit();return
    source_checksum=run.result.get('checksum')
    input_checksum=hashlib.sha256(json.dumps({'source_checksum':source_checksum,'seed':analysis.seed,'replicates':analysis.replicates,'tolerance':tolerance,'max_iterations':max_iterations,'cap_ratio':cap_ratio},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        draws=_resample(units,analysis.seed,analysis.replicates)
        replicate_rows=[];means=[];failures={}
        step=max(1,analysis.replicates//10)
        for i,counts in enumerate(draws,1):
            if i%step==0:
                analysis.result={'progress_done':i-1,'progress_total':analysis.replicates};db.commit()
            resampled=_replicate_units(units,counts)
            try:
                result=recalibrate(resampled,targets,tolerance,max_iterations,cap_ratio)
            except ValueError as exc:
                reason=str(exc)[:120] or '校准失败'
                failures[reason]=failures.get(reason,0)+1
                replicate_rows.append({'replicate':i,'weighted_mean':None,'converged':False,'failure':reason})
                continue
            except Exception as exc:
                reason='计算错误：'+str(exc)[:110]
                failures[reason]=failures.get(reason,0)+1
                replicate_rows.append({'replicate':i,'weighted_mean':None,'converged':False,'failure':reason})
                continue
            if not result['converged']:
                failures['未收敛']=failures.get('未收敛',0)+1
                replicate_rows.append({'replicate':i,'weighted_mean':None,'converged':False,'failure':'未收敛','max_residual':result['max_residual'],'iterations':result['iterations']})
                continue
            value=result['weighted_mean']
            if not math.isfinite(value):
                failures['加权均值非有限']=failures.get('加权均值非有限',0)+1
                replicate_rows.append({'replicate':i,'weighted_mean':None,'converged':False,'failure':'加权均值非有限'})
                continue
            means.append(value)
            replicate_rows.append({'replicate':i,'weighted_mean':value,'converged':True,'effective_sample_size':result['effective_sample_size'],'iterations':result['iterations'],'max_residual':result['max_residual']})
        valid=len(means)
        meta={'original_weighted_mean':run.result.get('weighted_mean'),'sample_count':len(units),'seed':analysis.seed,'source_checksum':source_checksum,'source_converged':bool(run.result.get('converged')),'input_checksum':input_checksum,'replicates_detail':replicate_rows,'method_note':'每份样本从原运行保留的样本中有放回抽取，重复抽中的观测按次数分别参与；沿用原目标边际及原容差、迭代上限与截断倍数逐份重新校准。仅计入收敛且均值为有限数的样本；未收敛或报错的样本排除。有效次数达到九成才报告百分位法95%区间（线性插值）。这是抽样波动下的描述性诊断，不覆盖未观测选择偏差，也不是对总体的严格推断。'}
        analysis.result=summarize(analysis.replicates,means,failures,meta)
        analysis.status='completed';analysis.error=None;db.commit()
    except Exception as exc:
        db.rollback();analysis=get_analysis(db,analysis_id)
        analysis.status='failed';analysis.error=f'重抽样计算失败：{str(exc)[:400]}';db.commit()
        raise
