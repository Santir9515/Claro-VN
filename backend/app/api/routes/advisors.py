from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.advisor import Advisor
from app.models.campaign import Campaign

router = APIRouter(prefix="/advisors", tags=["advisors"])


class AdvisorIn(BaseModel):
    name: str
    campaign_id: int


@router.post("")
def create_advisor(payload: AdvisorIn, db: Session = Depends(get_db)):
    camp = db.query(Campaign).filter(Campaign.id == payload.campaign_id).one_or_none()
    if camp is None:
        raise HTTPException(status_code=400, detail="campaign_id not found")

    a = Advisor(name=payload.name, campaign_id=payload.campaign_id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "name": a.name, "campaign_id": a.campaign_id}


@router.get("")
def list_advisors(campaign_id: int | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(Advisor)
    if campaign_id is not None:
        q = q.filter(Advisor.campaign_id == campaign_id)
    rows = q.order_by(Advisor.id.asc()).all()
    return [{"id": r.id, "name": r.name, "campaign_id": r.campaign_id} for r in rows]