from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.absence import Absence
from app.models.advisor import Advisor
from app.api.schemas import AbsenceUpsertIn, AbsenceOut

router = APIRouter(prefix="/absences", tags=["absences"])


@router.post("", response_model=AbsenceOut)
def upsert_absence(payload: AbsenceUpsertIn, db: Session = Depends(get_db)):
    adv = db.query(Advisor).filter(Advisor.id == payload.advisor_id).one_or_none()
    if adv is None:
        raise HTTPException(status_code=400, detail="advisor_id not found")

    row = (
        db.query(Absence)
        .filter(Absence.advisor_id == payload.advisor_id, Absence.day == payload.day)
        .one_or_none()
    )

    if row is None:
        row = Absence(advisor_id=payload.advisor_id, day=payload.day, is_absent=payload.is_absent)
        db.add(row)
    else:
        row.is_absent = payload.is_absent

    db.commit()
    return AbsenceOut(advisor_id=row.advisor_id, day=row.day, is_absent=row.is_absent)


@router.get("", response_model=list[AbsenceOut])
def list_absences(
    day: Optional[date_type] = Query(None),
    advisor_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    q = db.query(Absence)
    if day is not None:
        q = q.filter(Absence.day == day)
    if advisor_id is not None:
        q = q.filter(Absence.advisor_id == advisor_id)

    rows = q.order_by(Absence.day.asc(), Absence.advisor_id.asc()).all()
    return [AbsenceOut(advisor_id=r.advisor_id, day=r.day, is_absent=r.is_absent) for r in rows]