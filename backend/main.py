from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import asyncio
import sys

# Fix for Playwright/Subprocess on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from . import models, database, auditor, logger
from .database import engine, get_db

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="WCAG Auditor Fullstack")

# Simple Auth Security
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin123")

async def verify_token(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {AUTH_PASSWORD}":
        raise HTTPException(status_code=401, detail="No autorizado")

# Public Login
@app.post("/login")
async def login(data: dict):
    if data.get("password") == AUTH_PASSWORD:
        return {"token": AUTH_PASSWORD}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/logs")
async def get_app_logs(auth: None = Depends(verify_token)):
    return {"logs": logger.get_logs()}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def start_analysis(url: str, limit: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    name = f"Análisis: {url}"
    db_analysis = models.Analysis(main_url=url, name=name, status="pending")
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    
    task = auditor.WCAGAuditor(db_analysis.id)
    background_tasks.add_task(task.run_full_analysis, url, limit)
    
    return {"id": db_analysis.id, "status": "pending"}

@app.get("/history")
async def get_history(db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    return db.query(models.Analysis).order_by(models.Analysis.created_at.desc()).all()

@app.get("/analysis/{id}")
async def get_analysis(id: int, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    reports = db.query(models.PageReport).filter(models.PageReport.analysis_id == id).all()
    return {
        "analysis": analysis,
        "reports": reports
    }

@app.delete("/analysis/{id}")
async def delete_analysis(id: int, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    db.delete(analysis)
    db.commit()
    return {"status": "deleted"}

@app.put("/analysis/{id}")
async def update_analysis_name(id: int, name: str, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis.name = name
    db.commit()
    return {"status": "updated"}

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
