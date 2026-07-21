import os
import json
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.config import MEDIA_DIR
from app.db import collection, dataset_collection
from app.api.v1.analyze import router as analyze_router
from app.api.v1.dataset import router as dataset_router, build_advanced_mongo_query
from app.api.v1.history import router as history_router

app = FastAPI(
    title="Photocard Analysis & Dataset Service",
    version="1.0.0",
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

# Include Modular Routers
app.include_router(analyze_router, prefix="/api/v1", tags=["v1 Analysis"])
app.include_router(dataset_router, prefix="/api/v1", tags=["v1 Dataset Management"])
app.include_router(history_router, prefix="/api/v1", tags=["v1 History Management"])


# --- PAGE 1: LIVE ANALYSIS DASHBOARD (/logs) ---
@app.get("/logs", response_class=HTMLResponse)
async def view_log_book(filters: Optional[str] = Query(None)):
    filters_list = []
    if filters:
        for chunk in filters.split("|"):
            parts = chunk.split(":")
            if len(parts) == 3:
                filters_list.append({"mode": parts[0], "param": parts[1], "val": parts[2]})

    query = build_advanced_mongo_query(filters_list)
    
    total_db_count = await collection.count_documents({})
    matched_count = await collection.count_documents(query)
    clean_count = await collection.count_documents({**query, "status": "ok"})
    alert_count = await collection.count_documents({**query, "status": "alert"})
    low_conf_count = await collection.count_documents({**query, "status": "low_confidence"})

    cursor = collection.find(query, {"_id": 0}).sort("firstCapturedAt", -1)
    all_rows = await cursor.to_list(length=1000)

    # Filter Chips Rendering
    chips_html = ""
    for idx, f in enumerate(filters_list):
        mode_label = "IS" if f["mode"] == "inc" else "NOT"
        badge_class = "chip-inc" if f["mode"] == "inc" else "chip-exc"
        remaining = [f"{x['mode']}:{x['param']}:{x['val']}" for i, x in enumerate(filters_list) if i != idx]
        remove_url = f"/logs?filters={'|'.join(remaining)}" if remaining else "/logs"

        chips_html += f"""
        <div class="filter-chip {badge_class}" onclick="openEditFilterModal({idx}, '{f['mode']}', '{f['param']}', '{f['val']}')">
            <span class="chip-mode">{mode_label}</span>
            <span class="chip-text"><strong>{f['param']}</strong>: {f['val']}</span>
            <a href="{remove_url}" class="chip-remove" onclick="event.stopPropagation();">×</a>
        </div>
        """

    table_rows_html = ""
    cards_html = ""

    if all_rows:
        for index, row in enumerate(all_rows, start=1):
            first_time = row.get("firstCapturedAt", row.get("capturedAt", ""))
            last_time = row.get("lastCapturedAt", first_time)
            req_count = row.get("requestCount", 1)
            name = row.get("profileName", "Unknown Profile")
            p_url = row.get("profileUrl", "")
            pst_url = row.get("postUrl", "")
            priv = row.get("privacyType", "Unknown")
            post_time = row.get("postDatetime", "")
            img_url = row.get("imageUrl", "")
            stat = row.get("status", "low_confidence")

            badge_map = {
                "ok": '<span class="status-badge status-ok">🟢 Clean</span>',
                "alert": '<span class="status-badge status-alert">🔴 Alert</span>',
                "nothing_to_detect": '<span class="status-badge status-neutral">⚪ Neutral</span>',
                "low_confidence": '<span class="status-badge status-low">🟡 Low Confidence</span>'
            }
            status_badge = badge_map.get(stat, '<span class="status-badge status-low">🟡 Low Confidence</span>')

            img_cell = f'<a href="{img_url}" target="_blank" class="accent-link">🖼️ Media</a>' if img_url else '<span class="muted-text">No Media</span>'
            post_cell = f'<a href="{pst_url}" target="_blank" class="accent-link">🔗 Post</a>' if pst_url and pst_url.startswith("http") else '<span class="muted-text">N/A</span>'
            profile_cell = f'<a href="{p_url}" target="_blank" class="accent-link">👤 {name}</a>' if p_url and p_url.startswith("http") else f'<strong>{name}</strong>'

            table_rows_html += f"""
            <tr>
                <td><span class="serial-tag">#{index}</span></td>
                <td><span class="badge-count" title="Capture Count">×{req_count}</span></td>
                <td>{profile_cell}</td>
                <td>{post_cell}</td>
                <td><span class="badge">🔒 {priv}</span></td>
                <td>{status_badge}</td>
                <td><small class="time-stamp">{first_time}</small></td>
                <td><small class="muted-text">{last_time}</small></td>
                <td>{img_cell}</td>
            </tr>
            """

            img_preview = f'<img src="{img_url}" class="card-img" alt="Post Media"/>' if img_url else '<div class="no-img-box">No Media Asset</div>'
            cards_html += f"""
            <div class="card">
                <div class="card-media">
                    <span class="card-serial">#{index}</span>
                    <span class="card-count">×{req_count} requests</span>
                    {img_preview}
                </div>
                <div class="card-body">
                    <div class="card-header">
                        {profile_cell}
                        {status_badge}
                    </div>
                    <div class="card-meta">
                        <p><strong>Privacy:</strong> 🔒 {priv}</p>
                        <p><strong>First Seen:</strong> <span class="time-stamp">{first_time}</span></p>
                        <p><strong>Last Updated:</strong> {last_time}</p>
                    </div>
                    <div class="card-actions">
                        {post_cell}
                        {f'<a href="{img_url}" target="_blank" class="btn-sub">Open Image ↗</a>' if img_url else ''}
                    </div>
                </div>
            </div>
            """
    else:
        table_rows_html = '<tr><td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">No records found.</td></tr>'
        cards_html = '<div style="text-align: center; grid-column: 1/-1; padding: 40px; color: var(--text-muted);">No records found.</div>'

    download_query = f"filters_raw={filters}" if filters else ""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Analysis Engine — Live Logs</title>
        <style>
            :root {{
                --bg: #090D16; --panel: #111827; --card-bg: #111827;
                --text: #F9FAFB; --text-muted: #9CA3AF; --border: #1F2937;
                --primary: #3B82F6; --primary-hover: #2563EB;
                --success: #10B981; --danger: #EF4444; --warning: #F59E0B;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            
            .navbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; flex-wrap: wrap; gap: 16px; }}
            .brand h1 {{ margin: 0; font-size: 20px; font-weight: 800; tracking: -0.5px; }}
            .brand p {{ margin: 4px 0 0 0; font-size: 12px; color: var(--text-muted); }}

            .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
            .btn {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
            .btn:hover {{ border-color: var(--primary); }}
            .btn-primary {{ background: var(--primary); border-color: var(--primary); color: white; }}
            .btn-success {{ background: var(--success); border-color: var(--success); color: white; }}
            .btn-danger {{ background: var(--danger); border-color: var(--danger); color: white; }}
            .btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}

            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
            .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; display: flex; flex-direction: column; gap: 4px; }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px; }}
            .metric-num {{ font-size: 22px; font-weight: 800; color: #FFF; }}

            .chips-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; align-items: center; background: var(--panel); border: 1px solid var(--border); padding: 10px 16px; border-radius: 10px; }}
            .filter-chip {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid transparent; }}
            .chip-inc {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; border-color: rgba(16, 185, 129, 0.3); }}
            .chip-exc {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; border-color: rgba(239, 68, 68, 0.3); }}
            .chip-mode {{ text-transform: uppercase; font-size: 9px; padding: 2px 4px; border-radius: 4px; background: rgba(0,0,0,0.3); }}
            .chip-remove {{ text-decoration: none; color: inherit; font-size: 14px; font-weight: bold; margin-left: 4px; }}

            .table-wrapper {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
            th, td {{ padding: 12px 16px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
            th {{ background-color: rgba(15, 23, 42, 0.8); font-weight: 700; color: var(--text-muted); text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; position: sticky; top: 0; }}
            tr:hover {{ background-color: rgba(255, 255, 255, 0.02); }}

            .serial-tag {{ font-weight: 700; color: var(--primary); font-size: 12px; }}
            .badge-count {{ background: rgba(59, 130, 246, 0.15); color: #60A5FA; padding: 2px 6px; border-radius: 6px; font-size: 11px; font-weight: 800; border: 1px solid rgba(59, 130, 246, 0.3); }}
            .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; display: none; }}
            .card {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; position: relative; }}
            .card-media {{ height: 180px; background: #000; display: flex; align-items: center; justify-content: center; position: relative; border-bottom: 1px solid var(--border); }}
            .card-serial {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.8); color: var(--primary); padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 800; border: 1px solid var(--border); }}
            .card-count {{ position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.8); color: #60A5FA; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 800; border: 1px solid var(--border); }}
            .card-img {{ width: 100%; height: 100%; object-fit: cover; }}
            .no-img-box {{ color: var(--text-muted); font-size: 12px; }}
            .card-body {{ padding: 16px; display: flex; flex-direction: column; gap: 10px; justify-content: space-between; flex-grow: 1; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; }}
            .card-meta {{ font-size: 12px; color: var(--text-muted); margin: 0; }}
            .card-meta p {{ margin: 3px 0; }}
            .card-actions {{ display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-top: 8px; }}
            .btn-sub {{ color: var(--primary); text-decoration: none; font-weight: 700; }}
            
            .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }}
            .status-ok {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; }}
            .status-alert {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; }}
            .status-neutral {{ background-color: rgba(148, 163, 184, 0.15); color: #94A3B8; }}
            .status-low {{ background-color: rgba(245, 158, 11, 0.15); color: #FBBF24; }}
            .accent-link {{ color: var(--primary); text-decoration: none; font-weight: 600; }}
            .accent-link:hover {{ text-decoration: underline; }}
            .muted-text {{ color: var(--text-muted); font-size: 12px; }}
            .time-stamp {{ color: var(--primary); font-weight: 500; }}
            .badge {{ background-color: var(--bg); border: 1px solid var(--border); padding: 3px 6px; border-radius: 6px; font-size: 11px; color: var(--text-muted); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div class="brand">
                    <h1>📊 Photocard Stream Index</h1>
                    <p>Real-time Mongo Log Engine & Capture Monitoring</p>
                </div>
                <div class="controls">
                    <a href="/dataset-builder" class="btn btn-primary">🛠️ Open Dataset Studio</a>
                    <button id="listBtn" class="btn active" onclick="switchView('list')">☰ Table</button>
                    <button id="cardBtn" class="btn" onclick="switchView('card')">🔲 Grid</button>
                    <a href="/api/v1/dataset/download?format=json&{download_query}" class="btn">📥 JSON</a>
                    <a href="/api/v1/dataset/download?format=csv&{download_query}" class="btn btn-success">📥 CSV</a>
                    <button onclick="archiveAndClearLogs()" class="btn btn-danger">📦 Archive Logs</button>
                </div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card"><span class="metric-title">Total Active Logs</span><span class="metric-num">{total_db_count}</span></div>
                <div class="metric-card"><span class="metric-title">Matched Subset</span><span class="metric-num" style="color: var(--primary);">{matched_count}</span></div>
                <div class="metric-card"><span class="metric-title">Clean Records</span><span class="metric-num" style="color: var(--success);">{clean_count}</span></div>
                <div class="metric-card"><span class="metric-title">Threat Alerts</span><span class="metric-num" style="color: var(--danger);">{alert_count}</span></div>
                <div class="metric-card"><span class="metric-title">Low Confidence</span><span class="metric-num" style="color: var(--warning);">{low_conf_count}</span></div>
            </div>

            <div class="chips-container">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted);">ACTIVE FILTERS:</span>
                {chips_html if chips_html else '<span style="font-size: 12px; color: var(--text-muted);">Showing Complete Stream Index</span>'}
            </div>

            <div id="listView" class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Requests</th>
                            <th>Author Profile</th>
                            <th>Post URL</th>
                            <th>Privacy</th>
                            <th>Status</th>
                            <th>First Seen</th>
                            <th>Last Updated</th>
                            <th>Media Asset</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows_html}</tbody>
                </table>
            </div>

            <div id="cardView" class="cards-grid">{cards_html}</div>
        </div>

        <script>
            function switchView(view) {{
                const listView = document.getElementById('listView');
                const cardView = document.getElementById('cardView');
                const listBtn = document.getElementById('listBtn');
                const cardBtn = document.getElementById('cardBtn');

                if (view === 'list') {{
                    listView.style.display = 'block'; cardView.style.display = 'none';
                    listBtn.classList.add('active'); cardBtn.classList.remove('active');
                }} else {{
                    listView.style.display = 'none'; cardView.style.display = 'grid';
                    cardBtn.classList.add('active'); listBtn.classList.remove('active');
                }}
            }}

            function archiveAndClearLogs() {{
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;

                if (!confirm("Confirm archiving active logs into history and clearing the live log view?")) return;

                fetch('/api/v1/logs/archive-and-clear', {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{ alert(data.message); window.location.reload(); }})
                .catch(err => alert("Archive error: " + err));
            }}
        </script>
    </body>
    </html>
    """


# --- PAGE 2: FOCAL CARD-BY-CARD DATASET STUDIO (/dataset-builder) ---
@app.get("/dataset-builder", response_class=HTMLResponse)
async def view_dataset_builder():
    total_working_count = await dataset_collection.count_documents({})
    clean_count = await dataset_collection.count_documents({"status": "ok"})
    alert_count = await dataset_collection.count_documents({"status": "alert"})
    low_conf_count = await dataset_collection.count_documents({"status": "low_confidence"})
    verified_count = await dataset_collection.count_documents({"isVerifiedLabel": True})

    records = await dataset_collection.find({}, {"_id": 0}).sort("copiedAt", -1).to_list(length=10000)
    records_json = json.dumps(records)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dataset Studio — Focal Labeling Workspace</title>
        <style>
            :root {{
                --bg: #090D16; --panel: #111827; --border: #1F2937;
                --text: #F9FAFB; --muted: #9CA3AF; --primary: #3B82F6;
                --success: #10B981; --danger: #EF4444; --warning: #F59E0B;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
            .container {{ max-width: 1100px; margin: 0 auto; }}

            .navbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
            .brand h1 {{ font-size: 20px; margin: 0; font-weight: 800; }}
            .brand p {{ margin: 4px 0 0 0; font-size: 12px; color: var(--muted); }}

            .controls {{ display: flex; gap: 8px; align-items: center; }}
            .btn {{ background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
            .btn:hover {{ border-color: var(--primary); }}
            .btn-primary {{ background: var(--primary); border-color: var(--primary); color: white; }}
            .btn-success {{ background: var(--success); border-color: var(--success); color: white; }}

            .metrics-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }}
            .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 700; }}
            .metric-num {{ font-size: 20px; font-weight: 800; }}

            /* Focal Workspace */
            .focal-workspace {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 28px; display: flex; gap: 28px; align-items: center; min-height: 420px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }}
            .media-box {{ flex: 1; height: 380px; background: #000; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border); position: relative; }}
            .media-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
            .info-box {{ flex: 1; display: flex; flex-direction: column; gap: 16px; justify-content: space-between; height: 380px; }}

            .meta-group {{ font-size: 13px; color: var(--muted); display: flex; flex-direction: column; gap: 8px; }}
            .meta-group p {{ margin: 0; }}
            .meta-group strong {{ color: var(--text); }}

            .class-picker {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
            .cls-btn {{ padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: #1F2937; color: var(--text); font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; transition: all 0.15s ease; }}
            .cls-btn:hover {{ border-color: var(--primary); transform: translateY(-1px); }}
            .cls-btn.active {{ border-color: var(--primary); background: rgba(59, 130, 246, 0.2); color: #60A5FA; }}

            .nav-bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }}
            .progress-bar {{ flex: 1; height: 6px; background: var(--border); border-radius: 3px; margin: 0 20px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: var(--success); width: 0%; transition: width 0.3s ease; }}
            .counter-text {{ font-size: 13px; font-weight: 700; color: var(--muted); min-width: 80px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div class="brand">
                    <h1>🛠️ Dataset Studio — Focal Workspace</h1>
                    <p>One-by-One Item Labeling & Verification Engine</p>
                </div>
                <div class="controls">
                    <a href="/logs" class="btn">← Active Logs</a>
                    <button class="btn" onclick="importFromLogs()">📥 Import Copy</button>
                    <button class="btn" onclick="batchRename()">🏷️ Batch Rename</button>
                    <button class="btn btn-success" onclick="downloadZip()">📦 Export Dataset ZIP</button>
                </div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card"><span class="metric-title">Total Copy Items</span><span class="metric-num">{total_working_count}</span></div>
                <div class="metric-card"><span class="metric-title">Verified</span><span class="metric-num" style="color:var(--success);">{verified_count}</span></div>
                <div class="metric-card"><span class="metric-title">Clean</span><span class="metric-num" style="color:var(--success);">{clean_count}</span></div>
                <div class="metric-card"><span class="metric-title">Alert</span><span class="metric-num" style="color:var(--danger);">{alert_count}</span></div>
                <div class="metric-card"><span class="metric-title">Low Conf</span><span class="metric-num" style="color:var(--warning);">{low_conf_count}</span></div>
            </div>

            <div id="focalContainer" class="focal-workspace">
                <div class="media-box" id="mediaContainer">No Image</div>
                <div class="info-box">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span id="verifiedTag" style="font-size:11px; font-weight:800; color:var(--muted); text-transform:uppercase;">⏳ UNVERIFIED</span>
                            <span id="statusBadge" style="font-size:11px; font-weight:800; padding:2px 8px; border-radius:4px; background:var(--border);">LOW_CONFIDENCE</span>
                        </div>
                        <h2 id="authorName" style="margin: 8px 0 12px 0; font-size: 18px;">Profile Name</h2>
                        <div class="meta-group">
                            <p><strong>Post URL:</strong> <a id="postLink" href="#" target="_blank" style="color: var(--primary);">Open Post ↗</a></p>
                            <p><strong>Captured:</strong> <span id="capturedAt">-</span></p>
                            <p><strong>Privacy:</strong> <span id="privacyType">-</span></p>
                        </div>
                    </div>

                    <div>
                        <label style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase;">Assign ML Class Label:</label>
                        <div class="class-picker">
                            <div class="cls-btn" id="btn-ok" onclick="setLabel('ok')">🟢 Clean (ok)</div>
                            <div class="cls-btn" id="btn-alert" onclick="setLabel('alert')">🔴 Alert</div>
                            <div class="cls-btn" id="btn-nothing" onclick="setLabel('nothing_to_detect')">⚪ Neutral</div>
                            <div class="cls-btn" id="btn-low" onclick="setLabel('low_confidence')">🟡 Low Conf</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="nav-bar">
                <button class="btn" onclick="prevCard()">← Previous</button>
                <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
                <span class="counter-text" id="counterText">0 / 0</span>
                <button class="btn btn-primary" onclick="nextCard()">Next Item →</button>
            </div>
        </div>

        <script>
            const dataset = {records_json};
            let currentIndex = 0;

            function renderCurrentCard() {{
                if (!dataset || dataset.length === 0) {{
                    document.getElementById('focalContainer').innerHTML = "<div style='text-align:center; width:100%; color:var(--muted); padding:40px;'>Working dataset copy is currently empty. Click 'Import Copy' to load data.</div>";
                    return;
                }}

                const item = dataset[currentIndex];
                document.getElementById('authorName').innerText = item.profileName || "Unknown Profile";
                document.getElementById('postLink').href = item.postUrl || "#";
                document.getElementById('capturedAt').innerText = item.firstCapturedAt || item.capturedAt || "-";
                document.getElementById('privacyType').innerText = item.privacyType || "-";
                document.getElementById('verifiedTag').innerText = item.isVerifiedLabel ? "✅ VERIFIED" : "⏳ UNVERIFIED";
                document.getElementById('verifiedTag').style.color = item.isVerifiedLabel ? "#10B981" : "#9CA3AF";
                document.getElementById('statusBadge').innerText = (item.status || 'low_confidence').toUpperCase();
                
                document.getElementById('counterText').innerText = `${{currentIndex + 1}} of ${{dataset.length}}`;
                const progressPct = ((currentIndex + 1) / dataset.length) * 100;
                document.getElementById('progressFill').style.width = `${{progressPct}}%`;

                const mediaBox = document.getElementById('mediaContainer');
                if (item.imageUrl) {{
                    mediaBox.innerHTML = `<img src="${{item.imageUrl}}" alt="Media Asset"/>`;
                }} else {{
                    mediaBox.innerHTML = "<span style='color:var(--muted); font-size:13px;'>No Media Asset</span>";
                }}

                document.querySelectorAll('.cls-btn').forEach(btn => btn.classList.remove('active'));
                if (item.status === 'ok') document.getElementById('btn-ok').classList.add('active');
                if (item.status === 'alert') document.getElementById('btn-alert').classList.add('active');
                if (item.status === 'nothing_to_detect') document.getElementById('btn-nothing').classList.add('active');
                if (item.status === 'low_confidence') document.getElementById('btn-low').classList.add('active');
            }}

            function nextCard() {{
                if (currentIndex < dataset.length - 1) {{
                    currentIndex++;
                    renderCurrentCard();
                }}
            }}

            function prevCard() {{
                if (currentIndex > 0) {{
                    currentIndex--;
                    renderCurrentCard();
                }}
            }}

            function setLabel(newStatus) {{
                const item = dataset[currentIndex];
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;

                const formData = new FormData();
                formData.append('postUrl', item.postUrl);
                formData.append('new_status', newStatus);

                fetch('/api/v1/dataset/update-item-label', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    item.status = newStatus;
                    item.isVerifiedLabel = true;
                    renderCurrentCard();
                    nextCard();
                }});
            }}

            function importFromLogs() {{
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;
                fetch('/api/v1/dataset/create-working-copy?copy_name=working_v1', {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{ alert(data.message); window.location.reload(); }});
            }}

            function batchRename() {{
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;
                const prefix = prompt("Enter image prefix:", "photocard_batch");

                fetch(`/api/v1/dataset/batch-rename?prefix=${{encodeURIComponent(prefix)}}`, {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{ alert(data.message); window.location.reload(); }});
            }}

            function downloadZip() {{
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;
                fetch('/api/v1/dataset/generate-classification-zip', {{
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.blob())
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `dataset_${{Date.now()}}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }});
            }}

            renderCurrentCard();
        </script>
    </body>
    </html>
    """