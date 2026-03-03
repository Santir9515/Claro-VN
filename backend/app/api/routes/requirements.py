from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from openpyxl import load_workbook
from io import BytesIO
import re
from decimal import Decimal

from app.core.db import get_db
from app.models.requirements import Requirement

router = APIRouter(prefix="/requirements", tags=["requirements"])

WEEKDAY_MAP = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2, "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5, "sábado": 5,
    "domingo": 6,
}

H_COL_RE = re.compile(r"^H\d{4}$")

def hcol_to_min(col: str) -> int:
    hh = int(col[1:3])
    mm = int(col[3:5])
    return hh * 60 + mm

@router.post("/import")
async def import_requirements(
    campaign_id: int = Form(...),
    period: int = Form(...),
    sheet_name: str | None = Form(None),
    sheet_index: int = Form(0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    wb = load_workbook(filename=BytesIO(content), data_only=True)

    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise HTTPException(status_code=400, detail=f"sheet_name '{sheet_name}' not found")
        ws = wb[sheet_name]
    else:
        if sheet_index < 0 or sheet_index >= len(wb.sheetnames):
            raise HTTPException(status_code=400, detail=f"sheet_index out of range (0..{len(wb.sheetnames)-1})")
        ws = wb[wb.sheetnames[sheet_index]]

    header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    if not header or "Proceso" not in header or "Día" not in header:
        raise HTTPException(status_code=400, detail="Header inválido: debe contener 'Proceso' y 'Día'")

    col_idx = {name: i for i, name in enumerate(header) if isinstance(name, str)}
    proceso_i = col_idx.get("Proceso")
    dia_i = col_idx.get("Día")

    h_cols = [(name, i) for name, i in col_idx.items() if H_COL_RE.match(name)]
    if not h_cols:
        raise HTTPException(status_code=400, detail="No se encontraron columnas H0000..H2330")

    h_cols.sort(key=lambda x: hcol_to_min(x[0]))

    inserted = 0
    updated = 0
    weekday_rows: dict[int, int] = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        proceso = (row[proceso_i] or "")
        dia = (row[dia_i] or "")

        if not isinstance(proceso, str) or not isinstance(dia, str):
            continue

        if proceso.strip().lower() != "generales":
            continue

        dia_norm = dia.strip().lower()
        if dia_norm not in WEEKDAY_MAP:
            continue

        weekday = WEEKDAY_MAP[dia_norm]
        count_slots = 0

        for hname, hi in h_cols:
            val = row[hi]
            if val is None or val == "":
                continue

            minute = hcol_to_min(hname)

            try:
                req = Decimal(str(val))
            except Exception:
                raise HTTPException(status_code=400, detail=f"Valor inválido en {hname} ({dia}): {val}")

            existing = (
                db.query(Requirement)
                .filter(
                    Requirement.campaign_id == campaign_id,
                    Requirement.period == period,
                    Requirement.weekday == weekday,
                    Requirement.minute == minute,
                )
                .one_or_none()
            )

            if existing is None:
                db.add(
                    Requirement(
                        campaign_id=campaign_id,
                        period=period,
                        weekday=weekday,
                        minute=minute,
                        required=req,
                    )
                )
                inserted += 1
            else:
                if existing.required != req:
                    existing.required = req
                    updated += 1

            count_slots += 1

        weekday_rows[weekday] = weekday_rows.get(weekday, 0) + count_slots

    db.commit()

    return {
        "sheet": ws.title,
        "campaign_id": campaign_id,
        "period": period,
        "inserted": inserted,
        "updated": updated,
        "weekday_rows": weekday_rows,
    }
