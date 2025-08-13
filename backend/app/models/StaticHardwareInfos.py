from sqlalchemy import Column, Integer, String, DateTime, Float
from app.database import Base
from datetime import datetime



class StaticHardwareInfo(Base):
    __tablename__ = "static_hardware_infos"

    id = Column(Integer, primary_key=True, index=True)

    available_ram_gb = Column(Float, nullable=True)
    disk_total_gb = Column(Float, nullable=True)
    disk_avail_gb = Column(Float, nullable=True)
    cpu_model = Column(String, nullable=True)
    system_ram_gb = Column(Float, nullable=True)
    cpu_perf_units = Column(Float, nullable=True)
    global_inference_score = Column(Float, nullable=True) 
    global_inference_label = Column(String, nullable=True)
    global_finetuning_score = Column(Float, nullable=True)
    global_finetuning_label = Column(String, nullable=True)
    cpu_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=True)