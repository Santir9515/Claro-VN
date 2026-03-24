from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import and_
from sqlalchemy.orm import Session, aliased

from app.core.db import get_db
from app.models.advisor import Advisor
from app.models.shift import Shift
from app.models.absence import Absence
from app.core.timeutils import min_to_hhmm
from app.api.schemas import RosterRow

router = APIRouter(prefix="/roster", tags=["roster"])


@router.get("", response_model=list[RosterRow])
def roster(day: date, db: Session = Depends(get_db)):
    Sh = aliased(Shift)
    Ab = aliased(Absence)

    rows = (
        db.query(Advisor, Sh, Ab)
        .outerjoin(Sh, and_(Sh.advisor_id == Advisor.id, Sh.day == day))
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