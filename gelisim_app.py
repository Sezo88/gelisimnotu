"""
E-Okul Gelişim Düzeyleri Girişi - FastAPI Backend
Kullanıcı arayüzü ve otomasyon arasında köprü görevi görür.
"""

import os
import sys
import asyncio

if sys.platform == "win32":
    # Prevent Uvicorn from overriding ProactorEventLoopPolicy
    _original_set_policy = asyncio.set_event_loop_policy
    def _patched_set_policy(policy):
        if isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            return
        _original_set_policy(policy)
    asyncio.set_event_loop_policy = _patched_set_policy
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

import gelisim_automation as bot

app = FastAPI(title="E-Okul Gelişim Düzeyleri Girişi")


# ─── Static files ─────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    static_dir = os.path.join(sys._MEIPASS, "static")
else:
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def read_index():
    if getattr(sys, "frozen", False):
        index_path = os.path.join(sys._MEIPASS, "static", "index.html")
    else:
        index_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "static", "index.html"
        )
    return FileResponse(index_path)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/start-browser")
async def start_browser():
    """Launch headed browser and navigate to e-Okul login."""
    try:
        result = await bot.start_browser()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/navigate-gelisim")
async def navigate_gelisim():
    """Navigate to the Gelişim Düzeyleri Girişi page."""
    try:
        result = await bot.navigate_to_gelisim()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-subeler")
async def scan_subeler():
    """Scan the Şube dropdown."""
    try:
        result = await bot.scan_subeler()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SelectSubeRequest(BaseModel):
    subeValue: str


@app.post("/api/select-sube")
async def select_sube(req: SelectSubeRequest):
    """Select a Şube and return the Ders dropdown options."""
    try:
        result = await bot.select_sube_and_scan_dersler(req.subeValue)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SelectDersRequest(BaseModel):
    dersValue: str


@app.post("/api/select-ders-and-listele")
async def select_ders_and_listele(req: SelectDersRequest):
    """Select a Ders and click Listele."""
    try:
        result = await bot.select_ders_and_listele(req.dersValue)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-all-selects")
async def scan_all_selects():
    """Debug: scan all select elements on the page."""
    try:
        result = await bot.scan_all_selects()
        return {"selects": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-students")
async def scan_students():
    """Scan the student list."""
    try:
        students = await bot.scan_students()
        return {"students": students}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ClickStudentRequest(BaseModel):
    studentIndex: int


@app.post("/api/click-student")
async def click_student(req: ClickStudentRequest):
    """Click on a specific student to load their kazanımlar."""
    try:
        result = await bot.click_student(req.studentIndex)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-kazanimlar")
async def scan_kazanimlar():
    """Scan all kazanım sections and their radio options."""
    try:
        result = await bot.scan_kazanimlar()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChangeDonemRequest(BaseModel):
    donem: str

@app.post("/api/change-kazanim-donem")
async def change_kazanim_donem(req: ChangeDonemRequest):
    """Change the donem in the student panel and return new kazanimlar."""
    try:
        result = await bot.change_kazanim_donem(req.donem)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-page-structure")
async def scan_page_structure():
    """Deep scan the page DOM for analysis."""
    try:
        result = await bot.scan_full_page_structure()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ApplyRequest(BaseModel):
    students: List[Dict[str, Any]]
    selections: Dict[str, str] = {}
    donem: str = "2"
    random_mode: bool = False
    kazanim_groups: List[Dict[str, Any]] = []

@app.post("/api/apply-all")
async def apply_all(req: ApplyRequest):
    """Apply the selected kazanımlar to all students."""
    try:
        result = await bot.apply_selections_to_all(req.students, req.selections, req.donem, req.random_mode, req.kazanim_groups)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get current operation status."""
    return bot.current_status


@app.get("/api/logs")
async def get_logs():
    """Get all logs."""
    return {"logs": bot.logs}


@app.post("/api/clear-logs")
async def clear_logs():
    """Clear all logs."""
    bot.logs.clear()
    return {"status": "ok"}


@app.get("/api/page-html")
async def get_page_html():
    """Get the full page HTML for debugging."""
    try:
        html = await bot.get_page_html()
        return {"html": html}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
