from sqlalchemy import Column, Integer, SmallInteger, ForeignKey, Numeric, UniqueConstraint
from app.core.db import Base


class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    period = Column(Integer, nullable=False)
    weekday = Column(SmallInteger, nullable=False)   # 0=lunes..6=domingo
    minute = Column(SmallInteger, nullable=False)    # 0..1430
    required = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("campaign_id", "period", "weekday", "minute", name="uq_requirements"),
    )
