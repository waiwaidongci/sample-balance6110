import time,logging
from pathlib import Path
from src.config.database import SessionLocal
from src.config.queue import queue
from src.models import WeightRun,BootstrapAnalysis
from src.services.run_service import compute,QUEUE
from src.services.bootstrap_service import compute as compute_bootstrap,BOOTSTRAP_QUEUE
logging.basicConfig(level=logging.INFO)

def handle_bootstrap(item_id):
    with SessionLocal() as db:
        try:compute_bootstrap(db,int(item_id))
        except Exception:
            db.rollback();row=db.get(BootstrapAnalysis,int(item_id))
            if row and row.status!='failed':row.status='failed';row.error='重抽样计算失败，请重试';db.commit()
            logging.exception('bootstrap failed')

while True:
    Path('/tmp/heartbeat').touch()
    try:
        item=queue.blpop([QUEUE,BOOTSTRAP_QUEUE],timeout=4)
        if not item:continue
        if item[0]==BOOTSTRAP_QUEUE:handle_bootstrap(item[1]);continue
        with SessionLocal() as db:
            try:compute(db,int(item[1]))
            except Exception as exc:
                db.rollback();run=db.get(WeightRun,int(item[1]))
                if run:run.status='failed';run.error=str(exc)[:500];db.commit()
                logging.exception('calibration failed')
    except Exception:logging.exception('worker loop');time.sleep(2)
