from datetime import date
from pydantic import BaseModel, Field
from typing import Optional
from typing import Literal
from decimal import Decimal
from typing import Optional, List



class ComplianceSlotOut(BaseModel):
    minute: int = Field(ge=0, le=1410)   # 0..1410
    required: Optional[Decimal] = None
    planned_present: int = 0
    breaks_active: int = 0
    available: int = 0
    compliance: Optional[Decimal] = None  # available/required si required>0
    below_100: bool = False
    above_110: bool = False
    extras_needed: int = 0               # heads para llegar a 100%
    coaching_capacity_100: int = 0       # heads que podrías sacar y seguir >=100
    coaching_capacity_110: int = 0       # heads que podrías sacar y seguir >=110 (más conservador)


class ComplianceDayOut(BaseModel):
    campaign_id: int
    day: date
    period: int
    weekday: int
    minutes: List[int]
    slots: List[ComplianceSlotOut]

    # agregados (útiles para alertas / summary)
    slots_below_100: int
    slots_above_110: int
    max_extras_needed: int
    max_coaching_capacity_100: int

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

class BreakUpsertIn(BaseModel):
    advisor_id: int = Field(..., ge=1)
    day: date
    start: str  # "HH:MM"
    end: str    # "HH:MM"
    source: Literal["manual", "auto"] = "manual"

class BreakOut(BaseModel):
    id: int
    advisor_id: int
    day: date
    start_minute: int
    end_minute: int
    source: str

    class Config:
        from_attributes = True  # pydantic v2

class ComplianceSlotOut(BaseModel):
    minute: int = Field(ge=0, le=1410)   # 0..1410
    required: Optional[Decimal] = None
    planned_present: int = 0
    breaks_active: int = 0
    available: int = 0
    compliance: Optional[Decimal] = None  # available/required si required>0
    below_100: bool = False
    above_110: bool = False
    extras_needed: int = 0               # heads para llegar a 100%
    coaching_capacity_100: int = 0       # heads que podrías sacar y seguir >=100
    coaching_capacity_110: int = 0       # heads que podrías sacar y seguir >=110 (más conservador)
    in_scope: bool = False


class ComplianceDayOut(BaseModel):
    campaign_id: int
    day: date
    period: int
    weekday: int
    minutes: List[int]
    slots: List[ComplianceSlotOut]
    operational_only: bool
    minutes_eval: List[int]
    slots_below_100: int
    slots_above_110: int
    max_extras_needed: int
    max_coaching_capacity_100: int

