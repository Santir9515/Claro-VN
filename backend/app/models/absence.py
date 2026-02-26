from datetime import date, datetime

from sqlalchemy import ForeignKey, Date, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Absence(Base):
    __tablename__ = "absences"

    id: Mapped[int] = mapped_column(primary_key=True)

    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)

    is_absent: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # 1 registro de ausencia por asesor por día
        UniqueConstraint("advisor_id", "day", name="uq_absences_advisor_day"),
    )
