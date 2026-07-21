import os
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

# Include Routers
app.include_router(analyze_router, prefix="/api/v1", tags=["v1 Analysis"])
app.include_router(dataset_router, prefix="/api/v1", tags=["v1 Dataset Management"])
app.include_router(history_router, prefix="/api/v1", tags=["v1 History Management"])


# --- PAGE 1: ACTIVE LOGS DASHBOARD (/logs) ---
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

    cursor = collection.find(query, {"_id": 0}).sort("capturedAt", -1)
    all_rows = await cursor.to_list(length=1000)

    chips_html = ""
    for idx, f in enumerate(filters_list):
        mode_label = "IS" if f["mode"] == "inc" else "NOT"
        badge_class = "chip-inc" if f["mode"] == "inc" else "chip-exc"
        remaining = [f"{x['mode']}:{x['param']}:{x['val']}" for i, x in enumerate(filters_list) if i != idx]
        remove_url = f"/logs?filters={'|'.join(remaining)}" if remaining else "/logs"

        chips_html += f"""
        <div class="filter-chip {badge_class}" onclick="openEditFilterModal({idx}, '{f['mode']}', '{f['param']}', '{f['val']}')" title="Click to Edit Filter">
            <span class="chip-mode">{mode_label}</span>
            <span class="chip-text"><strong>{f['param']}</strong>: {f['val']}</span>
            <a href="{remove_url}" class="chip-remove" onclick="event.stopPropagation();" title="Delete Filter">×</a>
        </div>
        """

    table_rows_html = ""
    cards_html = ""

    if all_rows:
        for index, row in enumerate(all_rows, start=1):
            srv_time = row.get("capturedAt", "")
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

            img_cell = f'<a href="{img_url}" target="_blank" class="accent-link">🖼️ View Media</a>' if img_url else '<span class="muted-text">No Image</span>'
            post_cell = f'<a href="{pst_url}" target="_blank" class="accent-link">🔗 View Post</a>' if pst_url and pst_url.startswith("http") else '<span class="muted-text">N/A</span>'
            profile_cell = f'<a href="{p_url}" target="_blank" class="accent-link">👤 {name}</a>' if p_url and p_url.startswith("http") else f'<strong>{name}</strong>'

            table_rows_html += f"""
            <tr>
                <td><span class="serial-tag">#{index}</span></td>
                <td><small class="time-stamp">{srv_time}</small></td>
                <td>{profile_cell}</td>
                <td>{post_cell}</td>
                <td><span class="badge">🔒 {priv}</span></td>
                <td>{status_badge}</td>
                <td><small>{post_time}</small></td>
                <td>{img_cell}</td>
            </tr>
            """

            img_preview = f'<img src="{img_url}" class="card-img" alt="Post Media"/>' if img_url else '<div class="no-img-box">No Media Asset</div>'
            cards_html += f"""
            <div class="card">
                <div class="card-media">
                    <span class="card-serial">#{index}</span>
                    {img_preview}
                </div>
                <div class="card-body">
                    <div class="card-header">
                        {profile_cell}
                        {status_badge}
                    </div>
                    <div class="card-meta">
                        <p><strong>Privacy:</strong> 🔒 {priv}</p>
                        <p><strong>Created:</strong> {post_time}</p>
                        <p><strong>Captured:</strong> <span class="time-stamp">{srv_time}</span></p>
                    </div>
                    <div class="card-actions">
                        {post_cell}
                        {f'<a href="{img_url}" target="_blank" class="btn-sub">Open Image ↗</a>' if img_url else ''}
                    </div>
                </div>
            </div>
            """
    else:
        table_rows_html = '<tr><td colspan="8" style="text-align: center; padding: 40px; color: #888;">No matching records found.</td></tr>'
        cards_html = '<div style="text-align: center; grid-column: 1/-1; padding: 40px; color: #888;">No matching records found.</div>'

    download_query = f"filters_raw={filters}" if filters else ""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Analysis Analytics & Modern Dataset Hub</title>
        <style>
            :root {{
                --bg: #0F172A; --panel: #1E293B; --card-bg: #1E293B; --text: #F8FAFC;
                --text-muted: #94A3B8; --border: #334155; --primary: #3B82F6;
                --primary-hover: #2563EB; --success: #10B981; --danger: #EF4444; --warning: #F59E0B;
            }}
            body {{ font-family: -apple-system, system-ui, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 20px; flex-wrap: wrap; gap: 16px; }}
            h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 20px; }}
            .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; }}
            .metric-num {{ font-size: 20px; font-weight: 800; color: #FFF; }}
            .chips-container {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; align-items: center; background: var(--panel); border: 1px solid var(--border); padding: 12px 16px; border-radius: 10px; }}
            .filter-chip {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid transparent; }}
            .chip-inc {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; border-color: rgba(16, 185, 129, 0.3); }}
            .chip-exc {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; border-color: rgba(239, 68, 68, 0.3); }}
            .chip-mode {{ text-transform: uppercase; font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.25); }}
            .chip-remove {{ text-decoration: none; color: inherit; font-size: 16px; font-weight: bold; margin-left: 4px; }}
            .btn-add-filter {{ background-color: var(--primary); color: white; border: none; padding: 8px 16px; border-radius: 20px; font-size: 12px; font-weight: 700; cursor: pointer; }}
            .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
            .toggle-btn {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; }}
            .toggle-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
            .btn-action {{ background-color: var(--primary); color: white; text-decoration: none; border: none; padding: 9px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; }}
            .btn-success {{ background-color: var(--success); }}
            .btn-danger {{ background-color: var(--danger); }}
            .table-wrapper {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: auto; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
            th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
            th {{ background-color: rgba(15, 23, 42, 0.6); font-weight: 600; color: var(--text-muted); text-transform: uppercase; font-size: 11px; }}
            .serial-tag {{ font-weight: 700; color: var(--primary); font-size: 12px; }}
            .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; display: none; }}
            .card {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }}
            .card-media {{ height: 180px; background: var(--bg); display: flex; align-items: center; justify-content: center; position: relative; }}
            .card-serial {{ position: absolute; top: 10px; left: 10px; background: rgba(15, 23, 42, 0.85); color: var(--primary); padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 800; }}
            .card-img {{ width: 100%; height: 100%; object-fit: cover; }}
            .card-body {{ padding: 16px; display: flex; flex-direction: column; gap: 10px; justify-content: space-between; flex-grow: 1; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 14px; }}
            .card-meta {{ font-size: 12px; color: var(--text-muted); }}
            .card-actions {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-top: 8px; }}
            .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }}
            .status-ok {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; }}
            .status-alert {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; }}
            .status-neutral {{ background-color: rgba(148, 163, 184, 0.15); color: #94A3B8; }}
            .status-low {{ background-color: rgba(245, 158, 11, 0.15); color: #FBBF24; }}
            .accent-link {{ color: var(--primary); text-decoration: none; font-weight: 600; }}
            .muted-text {{ color: var(--text-muted); font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-bar">
                <div>
                    <h1>📊 Analysis Analytics & Modern Dataset Hub</h1>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Real-time Live Server Stream</p>
                </div>
                <div class="controls">
                    <a href="/dataset-builder" class="btn-action" style="background-color:#8B5CF6;">🛠️ Dataset Studio</a>
                    <button id="listBtn" class="toggle-btn active" onclick="switchView('list')">☰ List View</button>
                    <button id="cardBtn" class="toggle-btn" onclick="switchView('card')">🔲 Card View</button>
                    <a href="/api/v1/dataset/download?format=json&{download_query}" class="btn-action">📥 Export JSON</a>
                    <a href="/api/v1/dataset/download?format=csv&{download_query}" class="btn-action btn-success">📥 Export CSV</a>
                    <button onclick="archiveAndClearLogs()" class="btn-action btn-danger">📦 Archive & Clear Logs</button>
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
                <span style="font-size: 12px; font-weight: 700; color: var(--text-muted);">ACTIVE FILTERS:</span>
                {chips_html if chips_html else '<span style="font-size: 13px; color: var(--text-muted);">None (Displaying Complete Log Stream)</span>'}
                <button class="btn-add-filter" onclick="openAddFilterModal()">➕ Add Filter</button>
            </div>

            <div id="listView" class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Captured At</th>
                            <th>Author Profile</th>
                            <th>Post URL</th>
                            <th>Privacy Type</th>
                            <th>Analysis Status</th>
                            <th>Post Created At</th>
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

                if (!confirm("Confirm moving active logs to history archive and clearing live logs?")) return;

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


# --- PAGE 2: WORKING DATASET STUDIO (/dataset-builder) ---
@app.get("/dataset-builder", response_class=HTMLResponse)
async def view_dataset_builder():
    total_working_count = await dataset_collection.count_documents({})
    clean_count = await dataset_collection.count_documents({"status": "ok"})
    alert_count = await dataset_collection.count_documents({"status": "alert"})
    low_conf_count = await dataset_collection.count_documents({"status": "low_confidence"})

    records = await dataset_collection.find({}, {"_id": 0}).sort("copiedAt", -1).to_list(length=1000)

    rows_html = ""
    if records:
        for idx, row in enumerate(records, start=1):
            name = row.get("profileName", "Unknown Profile")
            pst_url = row.get("postUrl", "")
            img_url = row.get("imageUrl", "")
            stat = row.get("status", "low_confidence")
            verified = "✅ Verified" if row.get("isVerifiedLabel") else "⏳ Unverified"

            img_cell = f'<a href="{img_url}" target="_blank" style="color:#3B82F6;">🖼️ View Asset</a>' if img_url else 'No Image'

            rows_html += f"""
            <tr>
                <td><strong>#{idx}</strong></td>
                <td>{name}</td>
                <td><a href="{pst_url}" target="_blank" style="color:#3B82F6;">🔗 Post Link</a></td>
                <td>{img_cell}</td>
                <td>
                    <select onchange="updateLabel('{pst_url}', this.value)" style="padding:6px 10px; border-radius:6px; background:#0F172A; color:#FFF; border:1px solid #334155;">
                        <option value="ok" {"selected" if stat=="ok" else ""}>🟢 Clean (ok)</option>
                        <option value="alert" {"selected" if stat=="alert" else ""}>🔴 Alert</option>
                        <option value="nothing_to_detect" {"selected" if stat=="nothing_to_detect" else ""}>⚪ Neutral</option>
                        <option value="low_confidence" {"selected" if stat=="low_confidence" else ""}>🟡 Low Confidence</option>
                    </select>
                </td>
                <td><small style="color:#94A3B8;">{verified}</small></td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="6" style="text-align:center; padding:40px; color:#94A3B8;">Working dataset copy is currently empty. Click "Import Copy from Logs" to initialize.</td></tr>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Working Dataset Studio</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #0F172A; color: #F8FAFC; padding: 24px; margin: 0; }}
            .container {{ max-width: 1300px; margin: 0 auto; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 20px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }}
            .card {{ background: #1E293B; border: 1px solid #334155; padding: 16px; border-radius: 8px; }}
            .btn {{ background: #3B82F6; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; font-size: 13px; }}
            .btn-success {{ background: #10B981; }}
            table {{ width: 100%; border-collapse: collapse; background: #1E293B; border-radius: 8px; overflow: hidden; }}
            th, td {{ padding: 12px 16px; border-bottom: 1px solid #334155; text-align: left; font-size: 14px; }}
            th {{ background: #0F172A; color: #94A3B8; font-size: 11px; text-transform: uppercase; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1 style="margin:0;">🛠️ Working Dataset Studio</h1>
                    <p style="margin:4px 0 0 0; font-size:13px; color:#94A3B8;">Isolated Dataset Copy (Edits do not affect raw server logs)</p>
                </div>
                <div style="display:flex; gap:10px;">
                    <a href="/logs" class="btn" style="background:#475569;">← Active Server Logs</a>
                    <button class="btn" onclick="importFromLogs()">📥 Copy Data from Live Logs</button>
                    <button class="btn" onclick="batchRename()">🏷️ Batch Rename Images</button>
                    <button class="btn btn-success" onclick="downloadZip()">📦 Download Dataset ZIP</button>
                </div>
            </div>

            <div class="metrics">
                <div class="card"><span style="font-size:11px; color:#94A3B8;">TOTAL DATASET COPIES</span><br><strong style="font-size:20px;">{total_working_count}</strong></div>
                <div class="card"><span style="font-size:11px; color:#94A3B8;">CLEAN CLASS</span><br><strong style="font-size:20px; color:#10B981;">{clean_count}</strong></div>
                <div class="card"><span style="font-size:11px; color:#94A3B8;">ALERT CLASS</span><br><strong style="font-size:20px; color:#EF4444;">{alert_count}</strong></div>
                <div class="card"><span style="font-size:11px; color:#94A3B8;">LOW CONFIDENCE</span><br><strong style="font-size:20px; color:#F59E0B;">{low_conf_count}</strong></div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Author Profile</th>
                        <th>Post URL</th>
                        <th>Media Asset</th>
                        <th>ML Class Label</th>
                        <th>Verification</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>

        <script>
            function getAdminKey() {{ return prompt("🔒 Enter Admin Secret Key:"); }}

            function importFromLogs() {{
                const key = getAdminKey();
                if (!key) return;
                const copyName = prompt("Enter dataset copy name tag:", "working_dataset_v1");
                
                fetch(`/api/v1/dataset/create-working-copy?copy_name=${{encodeURIComponent(copyName)}}`, {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{ alert(data.message); window.location.reload(); }})
                .catch(err => alert("Failed: " + err));
            }}

            function updateLabel(postUrl, newStatus) {{
                const key = getAdminKey();
                if (!key) return;

                const formData = new FormData();
                formData.append('postUrl', postUrl);
                formData.append('new_status', newStatus);

                fetch('/api/v1/dataset/update-item-label', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{ console.log("Updated label:", data); }});
            }}

            function batchRename() {{
                const key = getAdminKey();
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
                const key = getAdminKey();
                if (!key) return;

                fetch('/api/v1/dataset/generate-classification-zip', {{
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.blob())
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `classification_dataset_${{Date.now()}}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }});
            }}
        </script>
    </body>
    </html>
    """