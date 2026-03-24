from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.advisor import Advisor
from app.models.shift import Shift
from app.models.absence import Absence
from app.models.breaks import Break
from app.models.requirements import Requirement
from app.workers.celery_app import celery_app


SLOT = 30  # minutos
WINDOW = 90  # minutos
TARGET = Decimal("1.0")


def _ceil_to_slot(x: int, slot: int = SLOT) -> int:
    return ((x + slot - 1) // slot) * slot


def _floor_to_slot(x: int, slot: int = SLOT) -> int:
    return (x // slot) * slot


def _period_yyyymm(d: date) -> int:
    return d.year * 100 + d.month


def _minutes_30m() -> List[int]:
    return list(range(0, 24 * 60, SLOT))  # 0..1410


@celery_app.task(name="assign_break")
def assign_break(advisor_id: int, day_iso: str) -> str:
    db: Session = SessionLocal()
    try:
        day = date.fromisoformat(day_iso)

        adv = db.query(Advisor).filter(Advisor.id == advisor_id).one_or_none()
        if adv is None:
            return f"skip: no advisor advisor_id={advisor_id}"

        campaign_id = adv.campaign_id
        period = _period_yyyymm(day)
        weekday = day.weekday()  # lunes=0 .. domingo=6

        sh_target = (
            db.query(Shift)
            .filter(Shift.advisor_id == advisor_id, Shift.day == day)
            .one_or_none()
        )
        if sh_target is None:
            return f"skip: no shift for advisor_id={advisor_id} day={day_iso}"

        # ventana válida
        win_start = sh_target.start_minute + WINDOW
        win_end = sh_target.end_minute - WINDOW - SLOT

        if win_end < win_start:
            # no hay ventana; fallback: centrar dentro del turno
            mid = (sh_target.start_minute + sh_target.end_minute) // 2
            c0 = _floor_to_slot(mid)
            candidates = [max(0, min(c0, 1410))]
        else:
            c_start = _ceil_to_slot(win_start)
            c_end = _floor_to_slot(win_end)
            candidates = list(range(c_start, c_end + 1, SLOT))

        minutes = _minutes_30m()

        # --- requerido ---
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

        if not required_by_min:
            chosen = candidates[0]
            _save_auto_break(db, advisor_id, day, chosen, chosen + SLOT)
            return f"ok: no requirements; break auto saved advisor_id={advisor_id} day={day_iso} start={chosen}"

        # --- asesores campaña con shift ese día ---
        shift_rows = (
            db.query(Shift.advisor_id, Shift.start_minute, Shift.end_minute)
            .join(Advisor, Advisor.id == Shift.advisor_id)
            .filter(Advisor.campaign_id == campaign_id, Shift.day == day)
            .all()
        )
        advisor_ids = [aid for (aid, _, _) in shift_rows]
        if not advisor_ids:
            return f"skip: no shifts for campaign_id={campaign_id} day={day_iso}"

        # ausencias
        abs_rows = (
            db.query(Absence.advisor_id, Absence.is_absent)
            .filter(Absence.day == day, Absence.advisor_id.in_(advisor_ids))
            .all()
        )
        absent_set = {aid for (aid, is_abs) in abs_rows if bool(is_abs)}

        # breaks existentes del día (manual + auto)
        br_rows = (
            db.query(Break.advisor_id, Break.start_minute, Break.end_minute, Break.source)
            .filter(Break.day == day, Break.advisor_id.in_(advisor_ids))
            .all()
        )

        # manuales del asesor objetivo (para no pisar)
        manual_target = [(s, e) for (aid, s, e, src) in br_rows if aid == advisor_id and src == "manual"]

        def overlaps_manual(start: int, end: int) -> bool:
            for s, e in manual_target:
                if not (end <= s or start >= e):
                    return True
            return False

        # planned_present por minuto (sin breaks)
        planned_present: Dict[int, int] = {m: 0 for m in minutes}
        for aid, s, e in shift_rows:
            if aid in absent_set:
                continue
            for m in minutes:
                if s <= m < e:
                    planned_present[m] += 1

        # breaks_count por minuto (breaks existentes)
        breaks_count: Dict[int, int] = {m: 0 for m in minutes}
        for aid, bs, be, _src in br_rows:
            if aid in absent_set:
                continue
            for m in minutes:
                if bs <= m < be:
                    breaks_count[m] += 1

        # === B) evaluamos solo minutos donde hay planificados ===
        minutes_eval = [m for m in minutes if planned_present[m] > 0]
        if not minutes_eval:
            chosen = candidates[0]
            _save_auto_break(db, advisor_id, day, chosen, chosen + SLOT)
            return f"ok: no planned_present in campaign; break auto saved advisor_id={advisor_id} day={day_iso} start={chosen}"

        # baseline (sin el break nuevo)
        baseline_def_by_min: Dict[int, Decimal] = {}
        baseline_comp_by_min: Dict[int, Decimal] = {}

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

        def eval_candidate_delta(c: int) -> Tuple[int, Decimal, Decimal]:
            """
            Retorna:
              newly_below_100: slots que pasan de >=100% a <100% por el break
              delta_deficit: incremento total de déficit por el break (daño marginal)
              min_comp_after: mínimo compliance después (desempate)
            """
            sim_breaks = dict(breaks_count)

            # sumar 1 break si corresponde y no estaba ya en break
            if advisor_id not in absent_set and sh_target.start_minute <= c < sh_target.end_minute:
                already_on_break = any(aid == advisor_id and bs <= c < be for (aid, bs, be, _src) in br_rows)
                if not already_on_break:
                    sim_breaks[c] += 1

            newly_below = 0
            delta_def = Decimal("0")
            min_after = Decimal("9999")

            for m in minutes_eval:
                req = required_by_min.get(m, Decimal("0"))
                if req <= 0:
                    comp_after = TARGET
                else:
                    available_after = Decimal(planned_present[m] - sim_breaks[m])
                    if available_after < 0:
                        available_after = Decimal("0")
                    comp_after = available_after / req

                if comp_after < min_after:
                    min_after = comp_after

                def_after = (TARGET - comp_after) if comp_after < TARGET else Decimal("0")
                def_before = baseline_def_by_min[m]

                # daño marginal
                if def_after > def_before:
                    delta_def += (def_after - def_before)

                # slots que se “rompen”
                if baseline_comp_by_min[m] >= TARGET and comp_after < TARGET:
                    newly_below += 1

            return (newly_below, delta_def, min_after)

        best = None
        best_score = None

        for c in candidates:
            start = c
            end = c + SLOT

            # no pisar manual
            if overlaps_manual(start, end):
                continue

            score = eval_candidate_delta(c)
            cmp_key = (score[0], score[1], -score[2])

            if best is None or cmp_key < best_score:
                best = c
                best_score = cmp_key

        if best is None:
            return f"skip: no feasible slot (manual overlaps) advisor_id={advisor_id} day={day_iso}"

        _save_auto_break(db, advisor_id, day, best, best + SLOT)
        return f"ok: break auto saved advisor_id={advisor_id} day={day_iso} start={best} end={best + SLOT}"

    finally:
        db.close()


def _save_auto_break(db: Session, advisor_id: int, day: date, start_minute: int, end_minute: int) -> None:
    db.query(Break).filter(
        Break.advisor_id == advisor_id,
        Break.day == day,
        Break.source == "auto",
    ).delete(synchronize_session=False)

    b = Break(
        advisor_id=advisor_id,
        day=day,
        start_minute=start_minute,
        end_minute=end_minute,
        source="auto",
    )
    db.add(b)
    db.commit()