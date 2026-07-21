import os
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.api.v1.analyze import router as v1_router, collection, build_mongo_query

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
async def view_log_book(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("all"),
    privacy: Optional[str] = Query("all"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("capturedAt"),
    sort_order: Optional[str] = Query("desc")
):
    query = build_mongo_query(search, status, privacy, start_date, end_date)
    sort_direction = -1 if sort_order == "desc" else 1

    cursor = collection.find(query, {"_id": 0}).sort(sort_by, sort_direction)
    all_rows = await cursor.to_list(length=1000)

    table_rows_html = ""
    cards_html = ""

    if all_rows:
        for row in all_rows:
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
                <div class="card-media">{img_preview}</div>
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
        table_rows_html = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #888;">No matching records found.</td></tr>'
        cards_html = '<div style="text-align: center; grid-column: 1/-1; padding: 40px; color: #888;">No matching records found.</div>'

    # Build download Query Strings using current filter parameters
    filter_params = f"search={search or ''}&status={status or 'all'}&privacy={privacy or 'all'}&start_date={start_date or ''}&end_date={end_date or ''}&sort_by={sort_by}&sort_order={sort_order}"

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
            .header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid var(--border); padding-bottom: 16px; flex-wrap: wrap; gap: 12px; }}
            h1 {{ margin: 0; font-size: 24px; }}
            .filter-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: end; }}
            .form-group {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: bold; }}
            .form-group input, .form-group select {{ padding: 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-size: 13px; }}
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
            .card {{ background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .card-media {{ height: 180px; background: var(--hover); display: flex; align-items: center; justify-content: center; overflow: hidden; border-bottom: 1px solid var(--border); }}
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
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #888;">Realtime Filtered Engine ({len(all_rows)} records displayed)</p>
                </div>
                <div class="controls">
                    <button id="listBtn" class="toggle-btn active" onclick="switchView('list')">☰ List View</button>
                    <button id="cardBtn" class="toggle-btn" onclick="switchView('card')">🔲 Card View</button>
                    <a href="/api/v1/dataset/download?format=json&{filter_params}" class="btn-action">📥 Download Filtered JSON</a>
                    <a href="/api/v1/dataset/download?format=csv&{filter_params}" class="btn-action btn-success">📥 Download Filtered CSV</a>
                </div>
            </div>

            <!-- Customization & Filtering Form -->
            <form method="GET" action="/logs" class="filter-card">
                <div class="form-group">
                    <label>Search Profile / Post</label>
                    <input type="text" name="search" value="{search or ''}" placeholder="Name or URL substring...">
                </div>
                <div class="form-group">
                    <label>Analysis Status</label>
                    <select name="status">
                        <option value="all" {"selected" if status == "all" else ""}>All Statuses</option>
                        <option value="ok" {"selected" if status == "ok" else ""}>🟢 Clean</option>
                        <option value="alert" {"selected" if status == "alert" else ""}>🔴 Alert</option>
                        <option value="nothing_to_detect" {"selected" if status == "nothing_to_detect" else ""}>⚪ Neutral</option>
                        <option value="low_confidence" {"selected" if status == "low_confidence" else ""}>🟡 Low Confidence</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Privacy Type</label>
                    <select name="privacy">
                        <option value="all" {"selected" if privacy == "all" else ""}>All Types</option>
                        <option value="Public" {"selected" if privacy == "Public" else ""}>Public</option>
                        <option value="Friends" {"selected" if privacy == "Friends" else ""}>Friends</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Start Date</label>
                    <input type="date" name="start_date" value="{start_date or ''}">
                </div>
                <div class="form-group">
                    <label>End Date</label>
                    <input type="date" name="end_date" value="{end_date or ''}">
                </div>
                <div class="form-group">
                    <label>Sort By</label>
                    <select name="sort_by">
                        <option value="capturedAt" {"selected" if sort_by == "capturedAt" else ""}>Captured At</option>
                        <option value="profileName" {"selected" if sort_by == "profileName" else ""}>Profile Name</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Sort Direction</label>
                    <select name="sort_order">
                        <option value="desc" {"selected" if sort_order == "desc" else ""}>Newest First (Desc)</option>
                        <option value="asc" {"selected" if sort_order == "asc" else ""}>Oldest First (Asc)</option>
                    </select>
                </div>
                <button type="submit" class="btn-action">🔍 Apply Filters</button>
            </form>

            <div id="listView" class="table-wrapper">
                <table>
                    <thead>
                        <tr>
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
        </script>
    </body>
    </html>
    """