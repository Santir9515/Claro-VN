from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.advisor import Advisor
from app.models.shift import Shift
from app.models.absence import Absence
from app.models.breaks import Break
from app.models.requirements import Requirement

router = APIRouter(prefix="/debug", tags=["debug"])

SLOT = 30
WINDOW = 90
TARGET = Decimal("1.0")


def ceil_to_slot(x: int) -> int:
    return ((x + SLOT - 1) // SLOT) * SLOT


def floor_to_slot(x: int) -> int:
    return (x // SLOT) * SLOT


def period_yyyymm(d: date) -> int:
    return d.year * 100 + d.month


@router.get("/assign_break")
def debug_assign_break(
    advisor_id: int = Query(..., ge=1),
    day: date = Query(...),
    db: Session = Depends(get_db),
):
    adv = db.query(Advisor).filter(Advisor.id == advisor_id).one_or_none()
    if not adv:
        raise HTTPException(400, "advisor not found")

    campaign_id = adv.campaign_id
    period = period_yyyymm(day)
    weekday = day.weekday()

    sh_target = (
        db.query(Shift)
        .filter(Shift.advisor_id == advisor_id, Shift.day == day)
        .one_or_none()
    )
    if not sh_target:
        raise HTTPException(400, "shift not found")

    # ventana válida
    win_start = sh_target.start_minute + WINDOW
    win_end = sh_target.end_minute - WINDOW - SLOT

    if win_end < win_start:
        candidates = []
    else:
        candidates = list(range(ceil_to_slot(win_start), floor_to_slot(win_end) + 1, SLOT))

    # requerido
    req_rows = (
        db.query(Requirement.minute, Requirement.required)
        .filter(
            Requirement.campaign_id == campaign_id,
            Requirement.period == period,
            Requirement.weekday == weekday,
        )
        .all()
    )
    required_by_min = {m: r for m, r in req_rows}

    if not required_by_min:
        return {
            "error": "no requirements for campaign/period/weekday",
            "campaign_id": campaign_id,
            "period": period,
            "weekday": weekday,
        }

    # shifts de campaña
    shift_rows = (
        db.query(Shift.advisor_id, Shift.start_minute, Shift.end_minute)
        .join(Advisor, Advisor.id == Shift.advisor_id)
        .filter(Advisor.campaign_id == campaign_id, Shift.day == day)
        .all()
    )
    advisor_ids = [aid for (aid, _, _) in shift_rows]
    if not advisor_ids:
        return {"error": "no shifts for campaign/day", "campaign_id": campaign_id, "day": day.isoformat()}

    # ausencias
    abs_rows = (
        db.query(Absence.advisor_id, Absence.is_absent)
        .filter(Absence.day == day, Absence.advisor_id.in_(advisor_ids))
        .all()
    )
    absent_set = {aid for (aid, is_abs) in abs_rows if bool(is_abs)}

    # breaks existentes
    br_rows = (
        db.query(Break.advisor_id, Break.start_minute, Break.end_minute, Break.source)
        .filter(Break.day == day, Break.advisor_id.in_(advisor_ids))
        .all()
    )

    manual_target = [
        (s, e) for (aid, s, e, src) in br_rows if aid == advisor_id and src == "manual"
    ]

    def overlaps_manual(start: int, end: int) -> bool:
        for s, e in manual_target:
            if not (end <= s or start >= e):
                return True
        return False

    minutes = list(range(0, 24 * 60, SLOT))  # 0..1410

    # planificados presentes
    planned_present = {m: 0 for m in minutes}
    for aid, s, e in shift_rows:
        if aid in absent_set:
            continue
        for m in minutes:
            if s <= m < e:
                planned_present[m] += 1

    # breaks existentes por minuto
    breaks_count = {m: 0 for m in minutes}
    for aid, bs, be, _src in br_rows:
        if aid in absent_set:
            continue
        for m in minutes:
            if bs <= m < be:
                breaks_count[m] += 1

    # === B: evaluar solo minutos donde hay planificados ===
    minutes_eval = [m for m in minutes if planned_present[m] > 0]
    if not minutes_eval:
        return {
            "advisor_id": advisor_id,
            "campaign_id": campaign_id,
            "day": day.isoformat(),
            "period": period,
            "weekday": weekday,
            "window_start": win_start,
            "window_end": win_end,
            "candidates": candidates,
            "manual_target": manual_target,
            "chosen": candidates[0] if candidates else None,
            "minutes_eval_count": 0,
            "minutes_eval_range": None,
            "scores": [],
            "note": "no planned_present>0 in campaign for this day",
        }

    minutes_eval_range = [min(minutes_eval), max(minutes_eval)]

    # baseline (sin break nuevo)
    baseline_def_by_min = {}
    baseline_comp_by_min = {}
    for m in minutes_eval:
        req = required_by_min.get(m, Decimal("0"))
        if req <= 0:
            comp = TARGET
        else:
            available = Decimal(planned_present[m] - breaks_count[m])
            if available < 0:
                available = Decimal("0")
            comp = available / req

        baseline_comp_by_min[m] = comp
        baseline_def_by_min[m] = (TARGET - comp) if comp < TARGET else Decimal("0")

    def eval_candidate_delta(c: int):
        sim = dict(breaks_count)

        # sumar break al slot c si aplica y no estaba ya en break
        if advisor_id not in absent_set and sh_target.start_minute <= c < sh_target.end_minute:
            already = any(aid == advisor_id and bs <= c < be for (aid, bs, be, _src) in br_rows)
            if not already:
                sim[c] += 1

        newly_below = 0
        delta_def = Decimal("0")
        min_after = Decimal("9999")

        for m in minutes_eval:
            req = required_by_min.get(m, Decimal("0"))
            if req <= 0:
                comp_after = TARGET
            else:
                available_after = Decimal(planned_present[m] - sim[m])
                if available_after < 0:
                    available_after = Decimal("0")
                comp_after = available_after / req

            if comp_after < min_after:
                min_after = comp_after

            def_after = (TARGET - comp_after) if comp_after < TARGET else Decimal("0")
            def_before = baseline_def_by_min[m]

            if def_after > def_before:
                delta_def += (def_after - def_before)

            if baseline_comp_by_min[m] >= TARGET and comp_after < TARGET:
                newly_below += 1

        return {
            "newly_below_100": newly_below,
            "delta_deficit": str(delta_def),
            "min_compliance_after": str(min_after),
        }

    scored = []
    feasible = []

    for c in candidates:
        item = {
            "start_minute": c,
            "end_minute": c + SLOT,
            "overlaps_manual": overlaps_manual(c, c + SLOT),
        }
        if not item["overlaps_manual"]:
            item.update(eval_candidate_delta(c))
            feasible.append(item)
        scored.append(item)

    chosen = None
    if feasible:
        feasible.sort(
            key=lambda x: (
                x["newly_below_100"],
                Decimal(x["delta_deficit"]),
                -Decimal(x["min_compliance_after"]),
            )
        )
        chosen = feasible[0]["start_minute"]

    return {
        "advisor_id": advisor_id,
        "campaign_id": campaign_id,
        "day": day.isoformat(),
        "period": period,
        "weekday": weekday,
        "window_start": win_start,
        "window_end": win_end,
        "candidates": candidates,
        "manual_target": manual_target,
        "chosen": chosen,
        "minutes_eval_count": len(minutes_eval),
        "minutes_eval_range": minutes_eval_range,
        "scores": scored,
    }