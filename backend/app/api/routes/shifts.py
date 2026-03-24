from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.workers.tasks import assign_break

from app.core.db import get_db
from app.core.timeutils import hhmm_to_min, min_to_hhmm
from app.models.shift import Shift
from app.models.advisor import Advisor
from app.api.schemas import ShiftUpsertIn, ShiftOut


router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.post("", response_model=ShiftOut)
def upsert_shift(payload: ShiftUpsertIn, db: Session = Depends(get_db)):
    try:
        start_min = hhmm_to_min(payload.start)
        end_min = hhmm_to_min(payload.end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if end_min <= start_min:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    adv = db.query(Advisor).filter(Advisor.id == payload.advisor_id).one_or_none()
    if adv is None:
        raise HTTPException(status_code=400, detail="advisor_id not found")

    row = (
        db.query(Shift)
        .filter(Shift.advisor_id == payload.advisor_id, Shift.day == payload.day)
        .one_or_none()
    )

    if row is None:
        row = Shift(
            advisor_id=payload.advisor_id,
            day=payload.day,
            start_minute=start_min,
            end_minute=end_min,
        )
        db.add(row)
    else:
        row.start_minute = start_min
        row.end_minute = end_min

    db.commit()

    # encolar task
    assign_break.apply_async(
        args=[payload.advisor_id, payload.day.isoformat()],
        countdown=1800,
    )

    return ShiftOut(
        advisor_id=payload.advisor_id,
        day=payload.day,
        start=min_to_hhmm(start_min),
        end=min_to_hhmm(end_min),
    )


@router.get("", response_model=list[ShiftOut])
def list_shifts(
    day: Optional[date_type] = Query(None),
    advisor_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    q = db.query(Shift)
    if day is not None:
        q = q.filter(Shift.day == day)
    if advisor_id is not None:
        q = q.filter(Shift.advisor_id == advisor_id)

    rows = q.order_by(Shift.day.asc(), Shift.advisor_id.asc()).all()
    return [
        ShiftOut(
            advisor_id=r.advisor_id,
            day=r.day,
            start=min_to_hhmm(r.start_minute),
            end=min_to_hhmm(r.end_minute),
        )
        for r in rows
    ]