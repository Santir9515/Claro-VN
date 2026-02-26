from datetime import date
from pydantic import BaseModel, Field
from typing import Optional

class ShiftUpsertIn(BaseModel):
    advisor_id: int
    day: date
    start: str = Field(..., description="HH:MM")
    end: str = Field(..., description="HH:MM")

class ShiftOut(BaseModel):
    advisor_id: int
    day: date
    start: str
    end: str

class AbsenceUpsertIn(BaseModel):
    advisor_id: int
    day: date
    is_absent: bool = True

class AbsenceOut(BaseModel):
    advisor_id: int
    day: date
    is_absent: bool

class RosterRow(BaseModel):
    advisor_id: int
    advisor_name: str
    day: date
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    is_absent: bool = False
