from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, aliased

from app.api.schemas import (
    ShiftUpsertIn,
    ShiftOut,
    AbsenceUpsertIn,
    AbsenceOut,
    RosterRow,
)
from app.core.db import get_db
from app.core.timeutils import hhmm_to_min, min_to_hhmm
from app.models.advisor import Advisor
from app.models.campaign import Campaign
from app.models.shift import Shift
from app.models.absence import Absence
from app.workers.break_tasks import assign_break

app = FastAPI(title="WFM Breaks MVP")


@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------
# CAMPAIGNS / ADVISORS
# -----------------------
class CampaignIn(BaseModel):
    name: str


class AdvisorIn(BaseModel):
    name: str
    campaign_id: int


@app.post("/campaigns")
def create_campaign(payload: CampaignIn, db: Session = Depends(get_db)):
    c = Campaign(name=payload.name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name}


@app.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.query(Campaign).order_by(Campaign.id.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@app.post("/advisors")
def create_advisor(payload: AdvisorIn, db: Session = Depends(get_db)):
    camp = db.query(Campaign).filter(Campaign.id == payload.campaign_id).one_or_none()
    if camp is None:
        raise HTTPException(status_code=400, detail="campaign_id not found")

    a = Advisor(name=payload.name, campaign_id=payload.campaign_id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "name": a.name, "campaign_id": a.campaign_id}


@app.get("/advisors")
def list_advisors(campaign_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Advisor)
    if campaign_id is not None:
        q = q.filter(Advisor.campaign_id == campaign_id)
    rows = q.order_by(Advisor.id.asc()).all()
    return [{"id": r.id, "name": r.name, "campaign_id": r.campaign_id} for r in rows]


# -----------------------
# SHIFTS (UPSERT + GET)
# -----------------------
@app.post("/shifts", response_model=ShiftOut)
def upsert_shift(payload: ShiftUpsertIn, db: Session = Depends(get_db)):
    # Validar que exista el advisor (evita 500 por FK)
    adv = db.query(Advisor).filter(Advisor.id == payload.advisor_id).one_or_none()
    if adv is None:
        raise HTTPException(status_code=400, detail="advisor_id not found")

    try:
        start_min = hhmm_to_min(payload.start)
        end_min = hhmm_to_min(payload.end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if end_min <= start_min:
        raise HTTPException(status_code=400, detail="end must be greater than start")

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

    # Encolar asignación de break +30 min (1800s)
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


@app.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    day: Optional[date_type] = None,
    advisor_id: Optional[int] = None,
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



# -----------------------
# ABSENCES (UPSERT + GET)
# -----------------------
@app.post("/absences", response_model=AbsenceOut)
def upsert_absence(payload: AbsenceUpsertIn, db: Session = Depends(get_db)):
    # Validar que exista el advisor (consistencia)
    adv = db.query(Advisor).filter(Advisor.id == payload.advisor_id).one_or_none()
    if adv is None:
        raise HTTPException(status_code=400, detail="advisor_id not found")

    row = (
        db.query(Absence)
        .filter(Absence.advisor_id == payload.advisor_id, Absence.day == payload.day)
        .one_or_none()
    )

    if row is None:
        row = Absence(
            advisor_id=payload.advisor_id,
            day=payload.day,
            is_absent=payload.is_absent,
        )
        db.add(row)
    else:
        row.is_absent = payload.is_absent

    db.commit()

    return AbsenceOut(
        advisor_id=payload.advisor_id,
        day=payload.day,
        is_absent=row.is_absent,
    )


@app.get("/absences", response_model=list[AbsenceOut])
def list_absences(
    day: Optional[date_type] = None,
    advisor_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Absence)
    if day is not None:
        q = q.filter(Absence.day == day)
    if advisor_id is not None:
        q = q.filter(Absence.advisor_id == advisor_id)

    rows = q.order_by(Absence.day.asc(), Absence.advisor_id.asc()).all()
    return [
        AbsenceOut(advisor_id=r.advisor_id, day=r.day, is_absent=r.is_absent)
        for r in rows
    ]


# -----------------------
# ROSTER (tabla maestra supervisor)
# -----------------------
@app.get("/roster", response_model=list[RosterRow])
def roster(day: date_type, campaign_id: Optional[int] = None, db: Session = Depends(get_db)):
    Sh = aliased(Shift)
    Ab = aliased(Absence)

    q = db.query(Advisor, Sh, Ab)

    if campaign_id is not None:
        q = q.filter(Advisor.campaign_id == campaign_id)

    rows = (
        q.outerjoin(Sh, and_(Sh.advisor_id == Advisor.id, Sh.day == day))
         .outerjoin(Ab, and_(Ab.advisor_id == Advisor.id, Ab.day == day))
         .order_by(Advisor.id.asc())
         .all()
    )

    out: list[RosterRow] = []
    for adv, sh, ab in rows:
        out.append(
            RosterRow(
                advisor_id=adv.id,
                advisor_name=adv.name,
                day=day,
                shift_start=min_to_hhmm(sh.start_minute) if sh else None,
                shift_end=min_to_hhmm(sh.end_minute) if sh else None,
                is_absent=bool(ab.is_absent) if ab else False,
            )
        )
    return out
