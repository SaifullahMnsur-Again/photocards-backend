import os
import urllib.parse
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List

from app.api.v1.analyze import router as v1_router, collection, build_advanced_mongo_query

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.include_router(v1_router, prefix="/api/v1", tags=["v1 Analysis"])

@app.get("/logs", response_class=HTMLResponse)
async def view_log_book(filters: Optional[str] = Query(None)):
    filters_list = []
    if filters:
        for chunk in filters.split("|"):
            parts = chunk.split(":")
            if len(parts) == 3:
                filters_list.append({"mode": parts[0], "param": parts[1], "val": parts[2]})

    query = build_advanced_mongo_query(filters_list)
    
    # Counts & Metrics
    total_db_count = await collection.count_documents({})
    matched_count = await collection.count_documents(query)
    clean_count = await collection.count_documents({**query, "status": "ok"})
    alert_count = await collection.count_documents({**query, "status": "alert"})
    low_conf_count = await collection.count_documents({**query, "status": "low_confidence"})

    cursor = collection.find(query, {"_id": 0}).sort("capturedAt", -1)
    all_rows = await cursor.to_list(length=1000)

    # Render Editable Filter Chips
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
            stat = row.get("status", "ok")

            badge_map = {
                "ok": '<span class="status-badge status-ok">🟢 Clean</span>',
                "alert": '<span class="status-badge status-alert">🔴 Alert</span>',
                "nothing_to_detect": '<span class="status-badge status-neutral">⚪ Neutral</span>',
                "low_confidence": '<span class="status-badge status-low">🟡 Low Confidence</span>'
            }
            status_badge = badge_map.get(stat, '<span class="status-badge status-neutral">⚪ Neutral</span>')

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
                --bg: #0F172A;
                --panel: #1E293B;
                --card-bg: #1E293B;
                --text: #F8FAFC;
                --text-muted: #94A3B8;
                --border: #334155;
                --primary: #3B82F6;
                --primary-hover: #2563EB;
                --success: #10B981;
                --danger: #EF4444;
                --warning: #F59E0B;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 24px;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            
            /* Header & Dashboard Stats Bar */
            .header-bar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                border-bottom: 1px solid var(--border);
                padding-bottom: 20px;
                flex-wrap: wrap;
                gap: 16px;
            }}
            h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
            
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
                gap: 12px;
                margin-bottom: 20px;
            }}
            .metric-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 12px 16px;
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; letter-spacing: 0.5px; }}
            .metric-num {{ font-size: 20px; font-weight: 800; color: #FFF; }}

            /* Active Chips Container */
            .chips-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 20px;
                align-items: center;
                background: var(--panel);
                border: 1px solid var(--border);
                padding: 12px 16px;
                border-radius: 10px;
            }}
            .filter-chip {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
                border: 1px solid transparent;
            }}
            .filter-chip:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
            .chip-inc {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; border-color: rgba(16, 185, 129, 0.3); }}
            .chip-exc {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; border-color: rgba(239, 68, 68, 0.3); }}
            .chip-mode {{ text-transform: uppercase; font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.25); }}
            .chip-remove {{ text-decoration: none; color: inherit; font-size: 16px; font-weight: bold; margin-left: 4px; border-radius: 50%; padding: 0 4px; }}
            .chip-remove:hover {{ background: rgba(255,255,255,0.2); }}

            .btn-add-filter {{
                background-color: var(--primary);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                transition: background 0.15s ease;
            }}
            .btn-add-filter:hover {{ background-color: var(--primary-hover); }}

            /* Modal Styling */
            .modal-overlay {{
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(15, 23, 42, 0.8);
                backdrop-filter: blur(4px);
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }}
            .modal-box {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 24px;
                max-width: 450px;
                width: 90%;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
                display: flex;
                flex-direction: column;
                gap: 16px;
            }}
            .modal-title {{ margin: 0; font-size: 18px; border-bottom: 1px solid var(--border); padding-bottom: 12px; font-weight: 700; }}
            .form-group {{ display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-muted); }}
            .form-group select, .form-group input {{ padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); font-size: 14px; outline: none; }}
            .form-group select:focus, .form-group input:focus {{ border-color: var(--primary); }}
            .modal-actions {{ display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px; }}

            /* Table and Cards */
            .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
            .toggle-btn {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; }}
            .toggle-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
            .btn-action {{ background-color: var(--primary); color: white; text-decoration: none; border: none; padding: 9px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; }}
            .btn-success {{ background-color: var(--success); }}
            
            .table-wrapper {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
            th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
            th {{ background-color: rgba(15, 23, 42, 0.6); font-weight: 600; color: var(--text-muted); position: sticky; top: 0; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
            tr:hover {{ background-color: rgba(255, 255, 255, 0.02); }}
            
            .serial-tag {{ font-weight: 700; color: var(--primary); font-size: 12px; }}
            .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; display: none; }}
            .card {{ background-color: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); position: relative; }}
            .card-media {{ height: 180px; background: var(--bg); display: flex; align-items: center; justify-content: center; overflow: hidden; border-bottom: 1px solid var(--border); position: relative; }}
            .card-serial {{ position: absolute; top: 10px; left: 10px; background: rgba(15, 23, 42, 0.85); color: var(--primary); padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 800; border: 1px solid var(--border); }}
            .card-img {{ width: 100%; height: 100%; object-fit: cover; }}
            .no-img-box {{ color: var(--text-muted); font-size: 13px; }}
            .card-body {{ padding: 16px; display: flex; flex-direction: column; gap: 10px; flex-grow: 1; justify-content: space-between; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 14px; gap: 8px; }}
            .card-meta {{ font-size: 12px; color: var(--text-muted); margin: 0; }}
            .card-meta p {{ margin: 3px 0; }}
            .card-actions {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-top: 8px; }}
            .btn-sub {{ color: var(--primary); text-decoration: none; font-size: 12px; font-weight: 700; }}
            .time-stamp {{ color: var(--primary); font-weight: 500; }}
            .badge {{ background-color: var(--bg); border: 1px solid var(--border); padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; color: var(--text-muted); }}
            
            .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }}
            .status-ok {{ background-color: rgba(16, 185, 129, 0.15); color: #34D399; }}
            .status-alert {{ background-color: rgba(239, 68, 68, 0.15); color: #F87171; }}
            .status-neutral {{ background-color: rgba(148, 163, 184, 0.15); color: #94A3B8; }}
            .status-low {{ background-color: rgba(245, 158, 11, 0.15); color: #FBBF24; }}
            
            .accent-link {{ color: var(--primary); text-decoration: none; font-weight: 600; }}
            .accent-link:hover {{ text-decoration: underline; }}
            .muted-text {{ color: var(--text-muted); font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header Bar -->
            <div class="header-bar">
                <div>
                    <h1>📊 Analysis Analytics & Modern Dataset Hub</h1>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Real-time MongoDB Engine Index</p>
                </div>
                <div class="controls">
                    <button id="listBtn" class="toggle-btn active" onclick="switchView('list')">☰ List View</button>
                    <button id="cardBtn" class="toggle-btn" onclick="switchView('card')">🔲 Card View</button>
                    <a href="/api/v1/dataset/download?format=json&{download_query}" class="btn-action">📥 Export JSON</a>
                    <a href="/api/v1/dataset/download?format=csv&{download_query}" class="btn-action btn-success">📥 Export CSV</a>
                </div>
            </div>

            <!-- Structured Metrics Banner -->
            <div class="metrics-grid">
                <div class="metric-card">
                    <span class="metric-title">Total System DB</span>
                    <span class="metric-num">{total_db_count}</span>
                </div>
                <div class="metric-card">
                    <span class="metric-title">Matched Subset</span>
                    <span class="metric-num" style="color: var(--primary);">{matched_count}</span>
                </div>
                <div class="metric-card">
                    <span class="metric-title">Clean Records</span>
                    <span class="metric-num" style="color: var(--success);">{clean_count}</span>
                </div>
                <div class="metric-card">
                    <span class="metric-title">Threat Alerts</span>
                    <span class="metric-num" style="color: var(--danger);">{alert_count}</span>
                </div>
                <div class="metric-card">
                    <span class="metric-title">Queued Training</span>
                    <span class="metric-num" style="color: var(--warning);">{low_conf_count}</span>
                </div>
            </div>

            <!-- Active Editable Filter Chips -->
            <div class="chips-container">
                <span style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Active Filters:</span>
                {chips_html if chips_html else '<span style="font-size: 13px; color: var(--text-muted);">None (Displaying Complete System Index)</span>'}
                <button class="btn-add-filter" onclick="openAddFilterModal()">➕ Add Filter</button>
                {f'<a href="/logs" class="muted-text" style="font-size: 12px; text-decoration: underline; margin-left: auto;">Reset All</a>' if filters else ''}
            </div>

            <!-- Filter Card Modal (Handles Creation & Editing) -->
            <div id="filterModal" class="modal-overlay">
                <div class="modal-box">
                    <h3 class="modal-title" id="modalTitle">➕ Add Custom Filter Rule</h3>
                    <div class="form-group">
                        <label>1. Condition Mode</label>
                        <select id="modalMode">
                            <option value="inc">IS / INCLUDE (Matches value)</option>
                            <option value="exc">NOT / EXCLUDE (Excludes value)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>2. Target Field</label>
                        <select id="modalParam" onchange="handleParamChange()">
                            <option value="status">Analysis Status</option>
                            <option value="privacyType">Privacy Type</option>
                            <option value="profileName">Profile Name</option>
                            <option value="postUrl">Post URL</option>
                            <option value="start_date">Start Date (GTE)</option>
                            <option value="end_date">End Date (LTE)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>3. Match Value</label>
                        <div id="modalValContainer">
                            <select id="modalValSelect">
                                <option value="ok">ok (🟢 Clean)</option>
                                <option value="alert">alert (🔴 Alert)</option>
                                <option value="nothing_to_detect">nothing_to_detect (⚪ Neutral)</option>
                                <option value="low_confidence">low_confidence (🟡 Low Confidence)</option>
                            </select>
                            <input type="text" id="modalValInput" style="display:none;" placeholder="Enter substring match...">
                            <input type="date" id="modalValDate" style="display:none;">
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button class="toggle-btn" onclick="closeFilterModal()">Cancel</button>
                        <button class="btn-action" onclick="saveFilterModal()">Save Filter Rule</button>
                    </div>
                </div>
            </div>

            <!-- Views -->
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
            let currentFilters = [];
            const rawFiltersString = "{filters or ''}";
            
            if (rawFiltersString) {{
                currentFilters = rawFiltersString.split('|').map(chunk => {{
                    const parts = chunk.split(':');
                    return {{ mode: parts[0], param: parts[1], val: parts[2] }};
                }});
            }}

            let editingIndex = -1; // -1 means adding new filter

            function switchView(view) {{
                const listView = document.getElementById('listView');
                const cardView = document.getElementById('cardView');
                const listBtn = document.getElementById('listBtn');
                const cardBtn = document.getElementById('cardBtn');

                if (view === 'list') {{
                    listView.style.display = 'block';
                    cardView.style.display = 'none';
                    listBtn.classList.add('active');
                    cardBtn.classList.remove('active');
                }} else {{
                    listView.style.display = 'none';
                    cardView.style.display = 'grid';
                    cardBtn.classList.add('active');
                    listBtn.classList.remove('active');
                }}
            }}

            function openAddFilterModal() {{
                editingIndex = -1;
                document.getElementById('modalTitle').innerText = "➕ Add Custom Filter Rule";
                document.getElementById('filterModal').style.display = 'flex';
                handleParamChange();
            }}

            function openEditFilterModal(index, mode, param, val) {{
                editingIndex = index;
                document.getElementById('modalTitle').innerText = "✏️ Edit Filter Rule";
                document.getElementById('modalMode').value = mode;
                document.getElementById('modalParam').value = param;
                
                handleParamChange();
                
                if (param === 'status' || param === 'privacyType') {{
                    document.getElementById('modalValSelect').value = val;
                }} else if (param === 'start_date' || param === 'end_date') {{
                    document.getElementById('modalValDate').value = val;
                }} else {{
                    document.getElementById('modalValInput').value = val;
                }}

                document.getElementById('filterModal').style.display = 'flex';
            }}

            function closeFilterModal() {{
                document.getElementById('filterModal').style.display = 'none';
            }}

            function handleParamChange() {{
                const param = document.getElementById('modalParam').value;
                const selectEl = document.getElementById('modalValSelect');
                const inputEl = document.getElementById('modalValInput');
                const dateEl = document.getElementById('modalValDate');

                selectEl.style.display = 'none';
                inputEl.style.display = 'none';
                dateEl.style.display = 'none';

                if (param === 'status') {{
                    selectEl.style.display = 'block';
                    selectEl.innerHTML = `
                        <option value="ok">ok (🟢 Clean)</option>
                        <option value="alert">alert (🔴 Alert)</option>
                        <option value="nothing_to_detect">nothing_to_detect (⚪ Neutral)</option>
                        <option value="low_confidence">low_confidence (🟡 Low Confidence)</option>
                    `;
                }} else if (param === 'privacyType') {{
                    selectEl.style.display = 'block';
                    selectEl.innerHTML = `
                        <option value="Public">Public</option>
                        <option value="Friends">Friends</option>
                    `;
                }} else if (param === 'start_date' || param === 'end_date') {{
                    dateEl.style.display = 'block';
                }} else {{
                    inputEl.style.display = 'block';
                }}
            }}

            function saveFilterModal() {{
                const mode = document.getElementById('modalMode').value;
                const param = document.getElementById('modalParam').value;
                
                let val = "";
                if (param === 'status' || param === 'privacyType') {{
                    val = document.getElementById('modalValSelect').value;
                }} else if (param === 'start_date' || param === 'end_date') {{
                    val = document.getElementById('modalValDate').value;
                }} else {{
                    val = document.getElementById('modalValInput').value.trim();
                }}

                if (!val) {{
                    alert("Please enter a valid filter match value.");
                    return;
                }}

                const newFilterObject = {{ mode, param, val }};

                if (editingIndex >= 0) {{
                    currentFilters[editingIndex] = newFilterObject;
                }} else {{
                    currentFilters.push(newFilterObject);
                }}

                const querySerialized = currentFilters.map(f => `${{f.mode}}:${{f.param}}:${{f.val}}`).join('|');
                window.location.href = `/logs?filters=${{encodeURIComponent(querySerialized)}}`;
            }}
        </script>
    </body>
    </html>
    """