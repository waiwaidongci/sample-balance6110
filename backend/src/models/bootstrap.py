from datetime import datetime
from sqlalchemy import ForeignKey,String,JSON,DateTime,Integer
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class BootstrapAnalysis(Base):
    __tablename__='bootstrap_analyses'
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey('weight_runs.id'))
    replicates:Mapped[int]=mapped_column(Integer)
    seed:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(20),default='queued')
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
