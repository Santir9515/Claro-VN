from sqlalchemy import Column, Integer, SmallInteger, Date, ForeignKey, DateTime, String, UniqueConstraint, func
from app.core.db import Base


class Break(Base):
    __tablename__ = "breaks"

    id = Column(Integer, primary_key=True)

    advisor_id = Column(Integer, ForeignKey("advisors.id", ondelete="CASCADE"), nullable=False)
    day = Column(Date, nullable=False)

    start_minute = Column(SmallInteger, nullable=False)  # 0..1439
    end_minute = Column(SmallInteger, nullable=False)    # > start_minute

    source = Column(String(16), nullable=False, server_default="auto")  # "auto" | "manual"

    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("advisor_id", "day", "start_minute", name="uq_breaks_advisor_day_start"),
    )