from datetime import date, datetime

from sqlalchemy import ForeignKey, Date, Integer, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)

    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)

    # minutos desde 00:00 (0..1440)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # 1 shift por asesor por día
        UniqueConstraint("advisor_id", "day", name="uq_shifts_advisor_day"),
        # validaciones básicas
        CheckConstraint("start_minute >= 0 AND start_minute < 1440", name="ck_shifts_start_minute_range"),
        CheckConstraint("end_minute > 0 AND end_minute <= 1440", name="ck_shifts_end_minute_range"),
        CheckConstraint("end_minute > start_minute", name="ck_shifts_end_gt_start"),
    )
