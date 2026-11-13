<script setup lang="ts">
import{ref,computed,onMounted}from 'vue';
import{getBootstraps,createBootstrap}from '../api/runs';
import type{BootstrapAnalysis}from '../types/domain';
import{useTask}from '../hooks/useTask';
import{usePolling}from '../hooks/usePolling';
import{number}from '../utils/format';
import StatusBadge from './common/StatusBadge.vue';
const props=defineProps<{runId:number;canRun:boolean}>();
const items=ref<BootstrapAnalysis[]>([]);
const form=ref({replicates:200,seed:20261113});
const{error,busy,execute}=useTask();
const pending=computed(()=>items.value.some(i=>['queued','running'].includes(i.status)));
const latest=computed(()=>items.value[0]||null);
const refresh=()=>execute(async()=>{items.value=await getBootstraps(props.runId)});
const submit=()=>execute(async()=>{await createBootstrap(props.runId,{replicates:form.value.replicates,seed:form.value.seed});await refresh()});
const reroll=()=>{form.value.seed=Math.floor(Math.random()*2147483647)};
onMounted(refresh);
usePolling(()=>{if(pending.value)refresh()});
</script>
<template>
<div class="section-heading"><h2>重抽样不确定性</h2><span>有放回抽取 · 逐份重新校准</span></div>
<p class="method-note">从本次结果的样本中有放回抽取同等数量的观测，重复抽中的样本按次数分别参与；沿用原目标边际与容差、迭代上限、截断倍数逐份重新校准。未收敛或计算失败的样本排除，成功不足九成时不报告95%均值区间。</p>
<form v-if="canRun" class="bootstrap-form" @submit.prevent="submit">
  <label>重抽样次数<input v-model.number="form.replicates" type="number" min="20" max="1000" step="1" required/></label>
  <label>随机种子<input v-model.number="form.seed" type="number" min="0" max="2147483647" step="1" required/></label>
  <button type="button" @click="reroll">换一个种子</button>
  <button class="primary" :disabled="busy||pending">{{pending?'排队计算中…':'提交重抽样 →'}}</button>
</form>
<p v-else class="method-note">只读角色可查看已计算的重抽样区间。</p>
<p v-if="error" class="error">{{error}}</p>
<template v-if="latest">
  <div v-if="latest.status==='completed'&&latest.result" class="bootstrap-summary">
    <div>
      <small>平均出行时长 / 95%区间</small>
      <b v-if="latest.result.interval">{{number(latest.result.interval.low)}} — {{number(latest.result.interval.high)}} 分钟</b>
      <b v-else class="bootstrap-blocked">未给出区间</b>
      <p v-if="latest.result.interval">百分位法 · 区间中位 {{number(latest.result.bootstrap_median)}} 分钟</p>
      <p v-else>有效次数 {{latest.result.valid_count}} / {{latest.result.replicates}}，未达九成（需 {{latest.result.required_for_interval}} 次），不报告95%均值区间。</p>
    </div>
    <div><small>有效次数 / 排除</small><b>{{latest.result.valid_count}} / {{latest.result.replicates}}</b><p>排除 {{latest.result.excluded_count}} 份 · 标准误 {{number(latest.result.bootstrap_std_error,3)}}</p></div>
    <div><small>原运行加权均值</small><b>{{number(latest.result.original_weighted_mean)}} 分钟</b><p>种子 {{latest.result.seed}} · 样本 {{latest.result.sample_count}}</p></div>
  </div>
  <p v-if="latest.status==='failed'" class="error">{{latest.error||'重抽样失败，请重试'}}</p>
  <p v-else-if="latest.status!=='completed'" class="empty">后台正在逐份重抽样与校准<span v-if="latest.result?.progress_total">（已处理 {{latest.result.progress_done??0}} / {{latest.result.progress_total}} 份）</span>；本页会自动刷新。</p>
  <template v-if="latest.status==='completed'&&latest.result">
    <div v-if="latest.result.failure_reasons?.length" class="failure-list"><small>排除原因</small><ul><li v-for="f in latest.result.failure_reasons" :key="f.reason">{{f.reason}} · {{f.count}} 份</li></ul></div>
    <p class="checksum">重抽样输入SHA256 / {{latest.result.input_checksum}}<br>原运行输入SHA256 / {{latest.result.source_checksum}}</p>
    <p class="method-note">{{latest.result.method_note}}</p>
  </template>
  <div class="table-wrap bootstrap-history">
    <table>
      <thead><tr><th>分析</th><th>状态</th><th>次数</th><th>种子</th><th>有效次数</th><th>95%区间 / 分钟</th></tr></thead>
      <tbody><tr v-for="a in items" :key="a.id"><td><small>BS / {{String(a.id).padStart(4,'0')}}</small></td><td><StatusBadge :status="a.status"/></td><td>{{a.replicates}}</td><td>{{a.seed}}</td><td>{{a.result?.valid_count??'—'}}</td><td>{{a.result?.interval?number(a.result.interval.low)+' — '+number(a.result.interval.high):'—'}}</td></tr></tbody>
    </table>
  </div>
</template>
</template>
