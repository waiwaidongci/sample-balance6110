from fastapi import APIRouter,Depends
from src.config.database import session
from src.middlewares.auth import current_user,require
from src.schemas.bootstrap import BootstrapInput
from src.services.bootstrap_service import list_analyses,get_analysis,create,_public
router=APIRouter(prefix='/bootstrap',tags=['bootstrap'])

@router.get('/runs/{run_id}')
def listing(run_id:int,db=Depends(session),user=Depends(current_user)):return list_analyses(db,run_id)

@router.post('/runs/{run_id}',status_code=201)
def creating(run_id:int,data:BootstrapInput,db=Depends(session),user=Depends(require('admin','analyst'))):return create(db,run_id,data,user)

@router.get('/{analysis_id}')
def detail(analysis_id:int,db=Depends(session),user=Depends(current_user)):return _public(get_analysis(db,analysis_id),full=True)
