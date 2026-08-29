from fastapi import FastAPI
from .config import APP_TITLE
from .db import SessionLocal
from .init_db import init_db
from .analytics import overview, monthly_trend, project_summary

app = FastAPI(title=APP_TITLE)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status":"ok","application":APP_TITLE}

@app.get("/api/overview")
def api_overview():
    db=SessionLocal()
    try:
        return overview(db)
    finally:
        db.close()

@app.get("/api/monthly")
def api_monthly():
    db=SessionLocal()
    try:
        return monthly_trend(db).to_dict(orient="records")
    finally:
        db.close()

@app.get("/api/projects")
def api_projects():
    db=SessionLocal()
    try:
        return project_summary(db).to_dict(orient="records")
    finally:
        db.close()
