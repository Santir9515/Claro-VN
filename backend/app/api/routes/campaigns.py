from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.campaign import Campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignIn(BaseModel):
    name: str


@router.post("")
def create_campaign(payload: CampaignIn, db: Session = Depends(get_db)):
    c = Campaign(name=payload.name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name}


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.query(Campaign).order_by(Campaign.id.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]