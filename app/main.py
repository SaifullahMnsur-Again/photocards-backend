import os
import json
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Literal

from app.config import MEDIA_DIR
from app.db import collection, history_collection, dataset_collection, projects_collection
from app.api.v1.analyze import router as analyze_router
from app.api.v1.dataset import router as dataset_router, build_advanced_mongo_query
from app.api.v1.history import router as history_router
from app.templates import render_logs_page, render_builder_page
from app.version import APP_VERSION

app = FastAPI(
    title="Photocard Analysis & Dataset Service",
    version=APP_VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# Include Routers
app.include_router(analyze_router, prefix="/api/v1", tags=["v1 Analysis"])
app.include_router(dataset_router, prefix="/api/v1", tags=["v1 Dataset Management"])
app.include_router(history_router, prefix="/api/v1", tags=["v1 History Management"])


# ==============================================================================
# PAGE 1: STREAM & ARCHIVE VIEWER DASHBOARD (/logs)
# ==============================================================================
@app.get("/logs", response_class=HTMLResponse)
async def view_log_book(
    filters: Optional[str] = Query(None),
    view_source: Literal["active", "archive"] = Query("active")
):
    filters_list = []
    if filters:
        for chunk in filters.split("|"):
            parts = chunk.split(":")
            if len(parts) == 3:
                filters_list.append({"mode": parts[0], "param": parts[1], "val": parts[2]})

    query = build_advanced_mongo_query(filters_list)
    target_coll = collection if view_source == "active" else history_collection
    
    total_db_count = await target_coll.count_documents({})
    matched_count = await target_coll.count_documents(query)
    clean_count = await target_coll.count_documents({**query, "status": "ok"})
    alert_count = await target_coll.count_documents({**query, "status": "alert"})
    low_conf_count = await target_coll.count_documents({**query, "status": "low_confidence"})

    cursor = target_coll.find(query, {"_id": 0}).sort("firstCapturedAt", -1)
    all_rows = await cursor.to_list(length=1000)

    chips_html = ""
    for idx, f in enumerate(filters_list):
        mode_label = "IS" if f["mode"] == "inc" else "NOT"
        badge_class = "chip-inc" if f["mode"] == "inc" else "chip-exc"
        remaining = [f"{x['mode']}:{x['param']}:{x['val']}" for i, x in enumerate(filters_list) if i != idx]
        remove_url = f"/logs?view_source={view_source}" + (f"&filters={'|'.join(remaining)}" if remaining else "")

        chips_html += f"""
        <div class="filter-chip {badge_class}">
            <span class="chip-mode">{mode_label}</span>
            <span class="chip-text"><strong>{f['param']}</strong>: {f['val']}</span>
            <a href="{remove_url}" class="chip-remove" onclick="event.stopPropagation();">×</a>
        </div>
        """

    raw_filters_param = filters or ""
    return render_logs_page(
        all_rows, view_source, total_db_count, matched_count, 
        clean_count, alert_count, low_conf_count, chips_html, raw_filters_param
    )


# ==============================================================================
# PAGE 2: MULTI-PROJECT DATASET STUDIO (/dataset-builder)
# ==============================================================================
@app.get("/dataset-builder", response_class=HTMLResponse)
async def view_dataset_builder(
    project_id: Optional[str] = Query(None),
    status_filter: str = Query("all"),
    class_filter: str = Query("all")
):
    projects = await projects_collection.find({}, {"_id": 0}).to_list(100)
    current_project = None
    items = []
    
    if projects:
        if not project_id:
            current_project = projects[0]
            project_id = current_project["projectId"]
        else:
            current_project = next((p for p in projects if p["projectId"] == project_id), projects[0])

        items = await dataset_collection.find({"projectId": project_id}, {"_id": 0}).to_list(10000)

    return render_builder_page(projects, current_project, items, status_filter, class_filter)