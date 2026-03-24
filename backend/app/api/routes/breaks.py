from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.breaks import Break

router = APIRouter(prefix="/breaks", tags=["breaks"])


class BreakOut(BaseModel):
    id: int
    advisor_id: int
    day: date
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    source: str

    class Config:
        from_attributes = True  # pydantic v2


class BreakUpsertIn(BaseModel):
    advisor_id: int = Field(ge=1)
    day: date
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    source: str = "manual"


@router.get("", response_model=list[BreakOut])
def list_breaks(
    day: date = Query(...),
    advisor_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    return (
        db.query(Break)
        .filter(Break.day == day, Break.advisor_id == advisor_id)
        .order_by(Break.start_minute.asc())
        .all()
    )


@router.post("", response_model=BreakOut)
def upsert_break(payload: BreakUpsertIn, db: Session = Depends(get_db)):
    if payload.end_minute <= payload.start_minute:
        raise HTTPException(status_code=400, detail="end_minute must be greater than start_minute")

    existing = (
        db.query(Break)
        .filter(
            Break.advisor_id == payload.advisor_id,
            Break.day == payload.day,
            Break.start_minute == payload.start_minute,
        )
        .one_or_none()
    )

    if existing is None:
        b = Break(
            advisor_id=payload.advisor_id,
            day=payload.day,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            source=payload.source,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        return b

    existing.end_minute = payload.end_minute
    existing.source = payload.source
    db.commit()
    db.refresh(existing)
    return existing