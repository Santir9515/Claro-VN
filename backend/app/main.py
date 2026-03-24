from fastapi import FastAPI

from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.advisors import router as advisors_router
from app.api.routes.shifts import router as shifts_router
from app.api.routes.absences import router as absences_router
from app.api.routes.roster import router as roster_router
from app.api.routes.requirements import router as requirements_router
from app.api.routes.breaks import router as breaks_router
from app.api.routes.debug_breaks import router as debug_router
from app.api.routes.metrics import router as metrics_router

app = FastAPI(title="WFM Breaks MVP")

app.include_router(campaigns_router)
app.include_router(advisors_router)
app.include_router(shifts_router)
app.include_router(absences_router)
app.include_router(roster_router)
app.include_router(requirements_router)
app.include_router(breaks_router)
app.include_router(debug_router)
app.include_router(metrics_router)

@app.get("/health")
def health():
    return {"status": "ok"}

