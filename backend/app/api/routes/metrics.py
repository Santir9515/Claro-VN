from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Dict, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.advisor import Advisor
from app.models.shift import Shift
from app.models.absence import Absence
from app.models.breaks import Break
from app.models.requirements import Requirement
from app.api.schemas import ComplianceDayOut, ComplianceSlotOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

SLOT = 30
TARGET_100 = Decimal("1.0")
TARGET_110 = Decimal("1.1")


def period_yyyymm(d: date) -> int:
    return d.year * 100 + d.month


def minutes_30m() -> List[int]:
    return list(range(0, 24 * 60, SLOT))  # 0..1410


def ceil_dec(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_CEILING))


def floor_dec(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_FLOOR))


@router.get("/compliance", response_model=ComplianceDayOut)
def compliance_day(
    campaign_id: int = Query(..., ge=1),
    day: date = Query(...),
    operational_only: bool = Query(True),  # default True
    db: Session = Depends(get_db),
):
    # valida campaña (existe al menos 1 advisor con esa campaña)
    exists = (
        db.query(Advisor.id)
        .filter(Advisor.campaign_id == campaign_id)
        .limit(1)
        .one_or_none()
    )
    if not exists:
        raise HTTPException(status_code=400, detail="campaign_id not found (no advisors)")

    period = period_yyyymm(day)
    weekday = day.weekday()
    minutes = minutes_30m()

    # requirements del día
    req_rows = (
        db.query(Requirement.minute, Requirement.required)
        .filter(
            Requirement.campaign_id == campaign_id,
            Requirement.period == period,
            Requirement.weekday == weekday,
        )
        .all()
    )
    required_by_min: Dict[int, Decimal] = {m: r for m, r in req_rows}

    # shifts campaña
    shift_rows = (
        db.query(Shift.advisor_id, Shift.start_minute, Shift.end_minute)
        .join(Advisor, Advisor.id == Shift.advisor_id)
        .filter(Advisor.campaign_id == campaign_id, Shift.day == day)
        .all()
    )
    advisor_ids = [aid for (aid, _, _) in shift_rows]

    # ausencias campaña
    absent_set = set()
    if advisor_ids:
        abs_rows = (
            db.query(Absence.advisor_id, Absence.is_absent)
            .filter(Absence.day == day, Absence.advisor_id.in_(advisor_ids))
            .all()
        )
        absent_set = {aid for (aid, is_abs) in abs_rows if bool(is_abs)}

    # breaks campaña
    br_rows = []
    if advisor_ids:
        br_rows = (
            db.query(Break.advisor_id, Break.start_minute, Break.end_minute, Break.source)
            .filter(Break.day == day, Break.advisor_id.in_(advisor_ids))
            .all()
        )

    # planned_present por minuto (sin breaks)
    planned_present: Dict[int, int] = {m: 0 for m in minutes}
    for aid, s, e in shift_rows:
        if aid in absent_set:
            continue
        for m in minutes:
            if s <= m < e:
                planned_present[m] += 1

    # breaks_active por minuto
    breaks_active: Dict[int, int] = {m: 0 for m in minutes}
    for aid, bs, be, _src in br_rows:
        if aid in absent_set:
            continue
        for m in minutes:
            if bs <= m < be:
                breaks_active[m] += 1

    # Scope para KPIs (no para el detalle de slots)
    # operacional_only=True => solo slots donde hay operación planificada
    minutes_eval = minutes
    if operational_only:
        minutes_eval = [m for m in minutes if planned_present[m] > 0]
    minutes_eval_set = set(minutes_eval)

    slots: List[ComplianceSlotOut] = []
    slots_below = 0
    slots_above = 0
    max_extras = 0
    max_coach_100 = 0

    for m in minutes:
        in_scope = (m in minutes_eval_set)

        req = required_by_min.get(m)  # puede ser None
        pp = planned_present[m]
        br = breaks_active[m]
        avail = pp - br
        if avail < 0:
            avail = 0

        comp = None
        below_100 = False
        above_110 = False
        extras_needed = 0
        coach_cap_100 = 0
        coach_cap_110 = 0

        if req is not None and req > 0:
            comp = (Decimal(avail) / req)

            below_100 = comp < TARGET_100
            above_110 = comp > TARGET_110

            # extras_needed: ceil(req - avail)
            need = req - Decimal(avail)
            extras_needed = ceil_dec(need) if need > 0 else 0

            # coaching_capacity_100: k <= avail - req
            cap100 = Decimal(avail) - req
            coach_cap_100 = floor_dec(cap100) if cap100 > 0 else 0

            # coaching_capacity_110: k <= avail - 1.1*req
            cap110 = Decimal(avail) - (TARGET_110 * req)
            coach_cap_110 = floor_dec(cap110) if cap110 > 0 else 0

        # KPIs SOLO EN SCOPE
        if in_scope:
            if below_100:
                slots_below += 1
            if above_110:
                slots_above += 1
            if extras_needed > max_extras:
                max_extras = extras_needed
            if coach_cap_100 > max_coach_100:
                max_coach_100 = coach_cap_100

        slots.append(
            ComplianceSlotOut(
                minute=m,
                required=req,
                planned_present=pp,
                breaks_active=br,
                available=avail,
                compliance=comp,
                below_100=below_100,
                above_110=above_110,
                extras_needed=extras_needed,
                coaching_capacity_100=coach_cap_100,
                coaching_capacity_110=coach_cap_110,
                in_scope=in_scope,
            )
        )

    return ComplianceDayOut(
        campaign_id=campaign_id,
        day=day,
        period=period,
        weekday=weekday,
        minutes=minutes,
        slots=slots,
        operational_only=operational_only,
        minutes_eval=minutes_eval,
        slots_below_100=slots_below,
        slots_above_110=slots_above,
        max_extras_needed=max_extras,
        max_coaching_capacity_100=max_coach_100,
    )