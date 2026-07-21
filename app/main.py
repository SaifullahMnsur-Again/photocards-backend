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
    
    total_db_count = await collection.count_documents({})
    matched_count = await collection.count_documents(query)

    cursor = collection.find(query, {"_id": 0}).sort("capturedAt", -1)
    all_rows = await cursor.to_list(length=1000)

    # Render Active Filter Cards / Badges
    chips_html = ""
    for idx, f in enumerate(filters_list):
        mode_label = "INCLUDE" if f["mode"] == "inc" else "EXCLUDE"
        badge_class = "chip-inc" if f["mode"] == "inc" else "chip-exc"
        
        # Build URL for removing this specific chip
        remaining = [f"{x['mode']}:{x['param']}:{x['val']}" for i, x in enumerate(filters_list) if i != idx]
        remove_url = f"/logs?filters={'|'.join(remaining)}" if remaining else "/logs"

        chips_html += f"""
        <div class="filter-chip {badge_class}">
            <span class="chip-mode">{mode_label}</span>
            <span class="chip-text"><strong>{f['param']}</strong>: {f['val']}</span>
            <a href="{remove_url}" class="chip-remove" title="Remove Filter">×</a>
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
                <td><strong>#{index}</strong></td>
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
        <title>Analysis Logs & Dataset Customizer</title>
        <style>
            :root {{ --bg: #f8f9fa; --card-bg: #ffffff; --text: #212529; --border: #dee2e6; --primary: #1877F2; --hover: #e4e6eb; }}
            @media (prefers-color-scheme: dark) {{
                :root {{ --bg: #18191A; --card-bg: #242526; --text: #E4E6EB; --border: #3E4042; --hover: #3A3B3C; }}
            }}
            body {{ font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 2px solid var(--border); padding-bottom: 16px; flex-wrap: wrap; gap: 12px; }}
            h1 {{ margin: 0; font-size: 24px; }}
            .metric-badge {{ background: var(--hover); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold; color: var(--primary); }}
            
            /* Filter Chips / Card Bar */
            .chips-container {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; align-items: center; }}
            .filter-chip {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; border: 1px solid var(--border); }}
            .chip-inc {{ background-color: rgba(40, 167, 69, 0.15); color: #28a745; border-color: rgba(40, 167, 69, 0.3); }}
            .chip-exc {{ background-color: rgba(220, 53, 69, 0.15); color: #dc3545; border-color: rgba(220, 53, 69, 0.3); }}
            .chip-mode {{ text-transform: uppercase; font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.1); }}
            .chip-remove {{ text-decoration: none; color: inherit; font-size: 16px; font-weight: bold; margin-left: 4px; cursor: pointer; }}
            .btn-add-filter {{ background-color: var(--primary); color: white; border: none; padding: 8px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }}

            /* Modal Styling */
            .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }}
            .modal-box {{ background: var(--card-bg); border-radius: 12px; padding: 24px; max-width: 450px; width: 90%; box-shadow: 0 10px 25px rgba(0,0,0,0.2); display: flex; flex-direction: column; gap: 16px; }}
            .modal-title {{ margin: 0; font-size: 18px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }}
            .form-group {{ display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: bold; }}
            .form-group select, .form-group input {{ padding: 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-size: 14px; }}
            .modal-actions {{ display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px; }}

            .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
            .toggle-btn {{ background: var(--hover); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; }}
            .toggle-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
            .btn-action {{ background-color: var(--primary); color: white; text-decoration: none; border: none; padding: 9px 14px; border-radius: 6px; font-weight: bold; font-size: 13px; cursor: pointer; text-align: center; }}
            .btn-success {{ background-color: #28a745; }}
            .table-wrapper {{ background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
            th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
            th {{ background-color: var(--hover); font-weight: 600; position: sticky; top: 0; }}
            tr:hover {{ background-color: var(--hover); }}
            .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; display: none; }}
            .card {{ background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.05); position: relative; }}
            .card-media {{ height: 180px; background: var(--hover); display: flex; align-items: center; justify-content: center; overflow: hidden; border-bottom: 1px solid var(--border); position: relative; }}
            .card-serial {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
            .card-img {{ width: 100%; height: 100%; object-fit: cover; }}
            .no-img-box {{ color: #888; font-size: 13px; }}
            .card-body {{ padding: 16px; display: flex; flex-direction: column; gap: 10px; flex-grow: 1; justify-content: space-between; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 14px; gap: 8px; }}
            .card-meta {{ font-size: 12px; color: #888; margin: 0; }}
            .card-meta p {{ margin: 3px 0; }}
            .card-actions {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-top: 8px; }}
            .btn-sub {{ color: var(--primary); text-decoration: none; font-size: 12px; font-weight: bold; }}
            .time-stamp {{ color: #1877f2; font-weight: 500; }}
            .badge {{ background-color: var(--hover); padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
            .status-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
            .status-ok {{ background-color: rgba(40, 167, 69, 0.15); color: #28a745; }}
            .status-alert {{ background-color: rgba(220, 53, 69, 0.15); color: #dc3545; }}
            .status-neutral {{ background-color: rgba(108, 117, 125, 0.15); color: #6c757d; }}
            .status-low {{ background-color: rgba(255, 193, 7, 0.2); color: #d39e00; }}
            .accent-link {{ color: var(--primary); text-decoration: none; font-weight: 500; }}
            .accent-link:hover {{ text-decoration: underline; }}
            .muted-text {{ color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-bar">
                <div>
                    <h1>📊 Analysis Logs & Dataset Customizer</h1>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #888;">
                        Total Records in DB: <span class="metric-badge">{total_db_count}</span> | 
                        Filtered Subset: <span class="metric-badge">{matched_count}</span>
                    </p>
                </div>
                <div class="controls">
                    <button id="listBtn" class="toggle-btn active" onclick="switchView('list')">☰ List View</button>
                    <button id="cardBtn" class="toggle-btn" onclick="switchView('card')">🔲 Card View</button>
                    <a href="/api/v1/dataset/download?format=json&{download_query}" class="btn-action">📥 Download Filtered JSON</a>
                    <a href="/api/v1/dataset/download?format=csv&{download_query}" class="btn-action btn-success">📥 Download Filtered CSV</a>
                </div>
            </div>

            <!-- Active Chips Container + Add Filter Trigger -->
            <div class="chips-container">
                <span style="font-size: 13px; font-weight: bold; color: #888;">Active Filter Cards:</span>
                {chips_html if chips_html else '<span style="font-size: 12px; color: #888;">None (Showing All Data)</span>'}
                <button class="btn-add-filter" onclick="openFilterModal()">➕ Add Filter Rule</button>
                {f'<a href="/logs" class="muted-text" style="font-size: 12px; text-decoration: underline; margin-left: auto;">Reset All Filters</a>' if filters else ''}
            </div>

            <!-- Add Filter Modal -->
            <div id="filterModal" class="modal-overlay">
                <div class="modal-box">
                    <h3 class="modal-title">➕ Add Custom Filter Rule</h3>
                    <div class="form-group">
                        <label>1. Filter Action Type</label>
                        <select id="modalMode">
                            <option value="inc">INCLUSION (Must Match / IS)</option>
                            <option value="exc">EXCLUSION (Must Not Match / NOT)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>2. Select Parameter</label>
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
                        <label>3. Parameter Value</label>
                        <div id="modalValContainer">
                            <select id="modalValSelect">
                                <option value="ok">ok (🟢 Clean)</option>
                                <option value="alert">alert (🔴 Alert)</option>
                                <option value="nothing_to_detect">nothing_to_detect (⚪ Neutral)</option>
                                <option value="low_confidence">low_confidence (🟡 Low Confidence)</option>
                            </select>
                            <input type="text" id="modalValInput" style="display:none;" placeholder="Enter matching value...">
                            <input type="date" id="modalValDate" style="display:none;">
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button class="toggle-btn" onclick="closeFilterModal()">Cancel</button>
                        <button class="btn-action" onclick="applyModalFilter()">Apply Filter Card</button>
                    </div>
                </div>
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
            const currentFiltersRaw = "{filters or ''}";

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

            function openFilterModal() {{
                document.getElementById('filterModal').style.display = 'flex';
                handleParamChange();
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

            function applyModalFilter() {{
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
                    alert("Please specify a valid value for the selected filter parameter.");
                    return;
                }}

                const newChunk = `${{mode}}:${{param}}:${{val}}`;
                const updatedFilters = currentFiltersRaw ? `${{currentFiltersRaw}}|${{newChunk}}` : newChunk;
                window.location.href = `/logs?filters=${{encodeURIComponent(updatedFilters)}}`;
            }}
        </script>
    </body>
    </html>
    """