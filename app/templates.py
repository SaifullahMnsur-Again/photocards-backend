import json
from app.version import APP_VERSION

def render_logs_page(all_rows, view_source, total_db_count, matched_count, clean_count, alert_count, low_conf_count, chips_html, raw_filters_param) -> str:
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

            img_cell = f'<a href="{img_url}" target="_blank" class="accent-link">🖼️ Media Asset</a>' if img_url else '<span class="muted-text">No Media</span>'
            post_cell = f'<a href="{pst_url}" target="_blank" class="accent-link">🔗 View Post</a>' if pst_url and pst_url.startswith("http") else '<span class="muted-text">N/A</span>'
            profile_cell = f'<a href="{p_url}" target="_blank" class="accent-link">👤 {name}</a>' if p_url and p_url.startswith("http") else f'<strong>{name}</strong>'

            delete_btn = f"""<button class="btn btn-danger" style="padding: 2px 6px; font-size: 11px;" onclick="deleteCapture('{pst_url}')">🗑️ Delete</button>""" if pst_url else ""

            table_rows_html += f"""
            <tr>
                <td><span class="serial-tag">#{index}</span></td>
                <td><span class="badge-count" title="Total Request Hits">×{req_count}</span></td>
                <td>{profile_cell}</td>
                <td>{post_cell}</td>
                <td><span class="badge">🔒 {priv}</span></td>
                <td>{status_badge}</td>
                <td><small class="time-stamp">{first_time}</small></td>
                <td><small class="muted-text">{last_time}</small></td>
                <td>{img_cell} {delete_btn}</td>
            </tr>
            """

            img_preview = f'<img src="{img_url}" class="card-img" alt="Post Media"/>' if img_url else '<div class="no-img-box">No Media Asset</div>'
            cards_html += f"""
            <div class="card">
                <div class="card-media">
                    <span class="card-serial">#{index}</span>
                    <span class="card-count">×{req_count} hits</span>
                    {img_preview}
                </div>
                <div class="card-body">
                    <div class="card-header">
                        {profile_cell}
                        {status_badge}
                    </div>
                    <div class="card-meta">
                        <p><strong>Privacy:</strong> 🔒 {priv}</p>
                        <p><strong>Post Date:</strong> {post_time}</p>
                        <p><strong>First Seen:</strong> <span class="time-stamp">{first_time}</span></p>
                        <p><strong>Last Updated:</strong> {last_time}</p>
                    </div>
                    <div class="card-actions">
                        {post_cell}
                        <div style="display:flex; gap:6px;">
                            {f'<a href="{img_url}" target="_blank" class="btn-sub">Asset ↗</a>' if img_url else ''}
                            {delete_btn}
                        </div>
                    </div>
                </div>
            </div>
            """
    else:
        table_rows_html = f'<tr><td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">No log entries found in {view_source.upper()} collection.</td></tr>'
        cards_html = f'<div style="text-align: center; grid-column: 1/-1; padding: 40px; color: var(--text-muted);">No log entries found in {view_source.upper()} collection.</div>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stream & Archive Hub v{APP_VERSION}</title>
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
            .brand h1 {{ margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }}
            .brand p {{ margin: 4px 0 0 0; font-size: 12px; color: var(--text-muted); }}

            .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
            .btn {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
            .btn:hover {{ border-color: var(--primary); }}
            .btn-primary {{ background: var(--primary); border-color: var(--primary); color: white; }}
            .btn-success {{ background: var(--success); border-color: var(--success); color: white; }}
            .btn-danger {{ background: var(--danger); border-color: var(--danger); color: white; }}
            .btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}

            .source-tabs {{ display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }}
            .source-tab {{ background: var(--panel); border: 1px solid var(--border); padding: 10px 18px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; color: var(--text-muted); text-decoration: none; display: flex; align-items: center; gap: 8px; }}
            .source-tab.active {{ background: var(--primary); border-color: var(--primary); color: white; }}

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

            .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(4px); }}
            .modal-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; width: 440px; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
            .modal-card h3 {{ margin: 0; font-size: 16px; font-weight: 700; }}
            .modal-card label {{ font-size: 12px; font-weight: 600; color: var(--text-muted); }}
            .modal-card input, .modal-card select {{ background: var(--bg); border: 1px solid var(--border); color: #FFF; padding: 10px; border-radius: 8px; font-size: 13px; outline: none; width: 100%; box-sizing: border-box; }}
            .modal-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div class="brand">
                    <h1>📊 Photocard Stream & Archive Hub</h1>
                    <p>Live Real-Time Stream Monitoring & Historical Archive Viewer v{APP_VERSION}</p>
                </div>
                <div class="controls">
                    <a href="/dataset-builder" class="btn btn-primary">🛠️ Open Dataset Studio</a>
                    <button id="listBtn" class="btn active" onclick="switchView('list')">☰ Table</button>
                    <button id="cardBtn" class="btn" onclick="switchView('card')">🔲 Grid</button>
                    <button class="btn btn-success" onclick="showModal('downloadModal')">📥 Export Logs</button>
                    {"<button onclick='archiveAndClearLogs()' class='btn btn-danger'>📦 Archive Active Logs</button>" if view_source == "active" else ""}
                </div>
            </div>

            <div class="source-tabs">
                <a href="/logs?view_source=active" class="source-tab {'active' if view_source == 'active' else ''}">
                    🔴 Active Stream Logs
                </a>
                <a href="/logs?view_source=archive" class="source-tab {'active' if view_source == 'archive' else ''}">
                    📦 Archive History Viewer
                </a>
            </div>

            <div class="metrics-grid">
                <div class="metric-card"><span class="metric-title">Total {view_source.title()} Logs</span><span class="metric-num">{total_db_count}</span></div>
                <div class="metric-card"><span class="metric-title">Matched Subset</span><span class="metric-num" style="color: var(--primary);">{matched_count}</span></div>
                <div class="metric-card"><span class="metric-title">Clean Records</span><span class="metric-num" style="color: var(--success);">{clean_count}</span></div>
                <div class="metric-card"><span class="metric-title">Threat Alerts</span><span class="metric-num" style="color: var(--danger);">{alert_count}</span></div>
                <div class="metric-card"><span class="metric-title">Low Confidence</span><span class="metric-num" style="color: var(--warning);">{low_conf_count}</span></div>
            </div>

            <div class="chips-container">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted);">ACTIVE FILTERS:</span>
                {chips_html if chips_html else f'<span style="font-size: 12px; color: var(--text-muted);">Showing Complete {view_source.title()} Collection</span>'}
                <button class="btn btn-primary" style="padding:4px 10px; font-size:11px; border-radius:20px;" onclick="showModal('addFilterModal')">➕ Add Filter</button>
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
                            <th>Media Asset & Actions</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows_html}</tbody>
                </table>
            </div>

            <div id="cardView" class="cards-grid">{cards_html}</div>
        </div>

        <div class="modal-overlay" id="addFilterModal">
            <div class="modal-card">
                <h3>➕ Add Stream Query Filter</h3>
                <div>
                    <label>Filter Target Parameter:</label>
                    <select id="flt_param">
                        <option value="status">Analysis Status (ok, alert, low_confidence)</option>
                        <option value="profileName">Profile Name</option>
                        <option value="privacyType">Privacy Type</option>
                        <option value="postUrl">Post URL</option>
                        <option value="start_date">Start Date (YYYY-MM-DD)</option>
                        <option value="end_date">End Date (YYYY-MM-DD)</option>
                    </select>
                </div>
                <div>
                    <label>Match Logic Condition:</label>
                    <select id="flt_mode">
                        <option value="inc">IS / CONTAINS (Include)</option>
                        <option value="exc">NOT / EXCLUDE</option>
                    </select>
                </div>
                <div>
                    <label>Filter Match Value:</label>
                    <input type="text" id="flt_val" placeholder="e.g. low_confidence or John Doe"/>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('addFilterModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="applyFilter()">Apply Filter</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="downloadModal">
            <div class="modal-card">
                <h3>📥 Export Log Records</h3>
                <div>
                    <label>Select Data Target Source:</label>
                    <select id="dl_source">
                        <option value="active" {"selected" if view_source == "active" else ""}>Active Stream Logs</option>
                        <option value="archive" {"selected" if view_source == "archive" else ""}>Archived Historical Database</option>
                        <option value="combined">Combined All Logs (Deduplicated)</option>
                    </select>
                </div>
                <div>
                    <label>Select Output File Format:</label>
                    <select id="dl_format">
                        <option value="json">JSON (Full Structural Metadata)</option>
                        <option value="csv">CSV (Spreadsheet Index with Media Links)</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('downloadModal')">Cancel</button>
                    <button class="btn btn-success" onclick="triggerLogDownload()">Download File</button>
                </div>
            </div>
        </div>

        <script>
            const currentRawFilters = "{raw_filters_param}";
            const activeViewSource = "{view_source}";

            function showModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
            function hideModal(id) {{ document.getElementById(id).style.display = 'none'; }}

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

            function applyFilter() {{
                const param = document.getElementById('flt_param').value;
                const mode = document.getElementById('flt_mode').value;
                const val = document.getElementById('flt_val').value.trim();

                if (!val) return;

                const newChunk = `${{mode}}:${{param}}:${{val}}`;
                const finalFilters = currentRawFilters ? `${{currentRawFilters}}|${{newChunk}}` : newChunk;
                window.location.href = `/logs?view_source=${{activeViewSource}}&filters=${{encodeURIComponent(finalFilters)}}`;
            }}

            function triggerLogDownload() {{
                const source = document.getElementById('dl_source').value;
                const format = document.getElementById('dl_format').value;
                hideModal('downloadModal');

                let targetUrl = `/api/v1/dataset/download?source=${{source}}&format=${{format}}`;
                if (currentRawFilters) targetUrl += `&filters_raw=${{encodeURIComponent(currentRawFilters)}}`;

                window.location.href = targetUrl;
            }}

            function deleteCapture(postUrl) {{
                if (!postUrl) return;
                const key = sessionStorage.getItem("adminSecretKey") || prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;

                if (!confirm("⚠️ Confirm permanently deleting this capture record AND its image file from server disk?")) return;

                fetch('/api/v1/logs/delete-capture?post_url=' + encodeURIComponent(postUrl) + '&source=' + activeViewSource, {{
                    method: 'DELETE',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.detail) alert("Delete error: " + data.detail);
                    else {{
                        alert("✅ Capture and associated image file removed successfully.");
                        window.location.reload();
                    }}
                }})
                .catch(err => alert("Delete error: " + err));
            }}

            function archiveAndClearLogs() {{
                const key = prompt("🔒 Enter Admin Secret Key:");
                if (!key) return;

                if (!confirm("Confirm archiving active logs into history and clearing live logs?")) return;

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

def render_builder_page(projects, current_project, items, status_filter, class_filter) -> str:
    total_items_count = len(items)
    verified_count = len([i for i in items if i.get("isVerified")])
    unverified_count = total_items_count - verified_count

    projects_json = json.dumps(projects)
    items_json = json.dumps(items)
    current_project_json = json.dumps(current_project) if current_project else "null"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dataset Studio v{APP_VERSION}</title>
        <style>
            :root {{
                --bg: #090D16; --panel: #111827; --border: #1F2937;
                --text: #F9FAFB; --muted: #9CA3AF; --primary: #3B82F6;
                --success: #10B981; --danger: #EF4444; --warning: #F59E0B;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}

            .navbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
            .brand h1 {{ font-size: 20px; margin: 0; font-weight: 800; }}
            .controls {{ display: flex; gap: 8px; align-items: center; }}

            .btn {{ background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
            .btn:hover {{ border-color: var(--primary); }}
            .btn-primary {{ background: var(--primary); border-color: var(--primary); color: white; }}
            .btn-success {{ background: var(--success); border-color: var(--success); color: white; }}
            .btn-danger {{ background: var(--danger); border-color: var(--danger); color: white; }}

            .auth-bar {{ display: flex; align-items: center; gap: 10px; background: var(--panel); border: 1px solid var(--border); padding: 8px 16px; border-radius: 10px; margin-bottom: 20px; }}
            .auth-bar input {{ background: var(--bg); border: 1px solid var(--border); color: #FFF; padding: 6px 12px; border-radius: 6px; font-size: 13px; outline: none; width: 220px; }}

            .metrics-bar {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }}
            .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 700; }}
            .metric-num {{ font-size: 20px; font-weight: 800; }}

            .class-distribution-bar {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 20px; }}
            .class-dist-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 12px; font-weight: 800; color: var(--muted); text-transform: uppercase; }}
            .class-chips-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
            .class-chip {{ background: var(--bg); border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.15s ease; color: var(--text); }}
            .class-chip:hover {{ border-color: var(--primary); }}
            .class-chip.active {{ background: rgba(59, 130, 246, 0.2); border-color: var(--primary); color: #60A5FA; }}
            .class-chip.unassigned-chip.active {{ background: rgba(239, 68, 68, 0.2); border-color: var(--danger); color: #F87171; }}
            .class-count-badge {{ background: #1F2937; color: #FFF; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 800; }}

            .project-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; gap: 12px; }}
            .project-tabs {{ display: flex; gap: 10px; overflow-x: auto; }}
            .project-tab {{ background: var(--panel); border: 1px solid var(--border); padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; white-space: nowrap; }}
            .project-tab.active {{ background: var(--primary); border-color: var(--primary); color: white; }}

            .status-filter-bar {{ display: flex; gap: 10px; margin-bottom: 20px; background: var(--panel); border: 1px solid var(--border); padding: 6px 12px; border-radius: 10px; align-items: center; }}
            .status-btn {{ padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 700; border: 1px solid transparent; cursor: pointer; color: var(--muted); background: transparent; }}
            .status-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}

            .focal-workspace {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 28px; min-height: 400px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); position: relative; display: flex; align-items: center; justify-content: center; }}
            .empty-workspace-banner {{ text-align: center; width: 100%; color: var(--muted); font-size: 15px; font-weight: 700; padding: 60px 20px; display: none; }}
            .card-workspace-content {{ display: flex; gap: 28px; width: 100%; align-items: center; }}

            .media-box {{ flex: 1; height: 360px; background: #000; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border); position: relative; }}
            .media-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
            .info-box {{ flex: 1; display: flex; flex-direction: column; gap: 12px; justify-content: space-between; height: 360px; }}

            .class-picker {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; margin-top: 10px; }}
            .cls-btn {{ padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: #1F2937; color: var(--text); font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; text-transform: capitalize; transition: all 0.15s ease; }}
            .cls-btn:hover {{ border-color: var(--primary); transform: translateY(-1px); }}
            .cls-btn.active {{ border-color: var(--primary); background: rgba(59, 130, 246, 0.2); color: #60A5FA; }}

            .nav-bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }}
            .progress-bar {{ flex: 1; height: 6px; background: var(--border); border-radius: 3px; margin: 0 20px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: var(--success); width: 0%; transition: width 0.3s ease; }}

            .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(4px); }}
            .modal-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; width: 440px; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
            .modal-card h3 {{ margin: 0; font-size: 16px; font-weight: 700; }}
            .modal-card label {{ font-size: 12px; font-weight: 600; color: var(--muted); }}
            .modal-card input, .modal-card textarea, .modal-card select {{ background: var(--bg); border: 1px solid var(--border); color: #FFF; padding: 10px; border-radius: 8px; font-size: 13px; outline: none; width: 100%; box-sizing: border-box; }}
            .modal-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }}

            .filename-box {{ background: var(--bg); border: 1px solid var(--border); padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; color: #A7F3D0; word-break: break-all; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div class="brand">
                    <h1>🛠️ Dataset Studio <small style="font-size:12px; color:var(--muted);">v{APP_VERSION}</small></h1>
                </div>
                <div class="controls">
                    <a href="/logs" class="btn">← Live Stream / Archives</a>
                    <button class="btn btn-primary" onclick="showModal('newProjectModal')">➕ New Project</button>
                    <button class="btn" onclick="showModal('importModal')">🔄 Sync / Import Data</button>
                    <button class="btn" onclick="batchRenameClassified()" title="Apply structured monotonic filenames to existing classified items">🏷️ Batch Rename Existing</button>
                    <button class="btn btn-success" onclick="showModal('exportModal')">📦 Export ZIP</button>
                </div>
            </div>

            <div class="auth-bar">
                <span style="font-size:12px; font-weight:700; color:var(--muted);">🔒 SESSION ADMIN KEY:</span>
                <input type="password" id="adminSecretKey" placeholder="Enter key once..." onchange="saveAdminKey(this.value)"/>
                <span id="authStatus" style="font-size:12px; font-weight:700; color:var(--muted);"></span>
            </div>

            <div class="metrics-bar">
                <div class="metric-card"><span class="metric-title">Project Total</span><span class="metric-num" id="cnt_total">{total_items_count}</span></div>
                <div class="metric-card"><span class="metric-title">Unverified / Unclassed</span><span class="metric-num" id="cnt_unverified" style="color:var(--danger);">{unverified_count}</span></div>
                <div class="metric-card"><span class="metric-title">Verified / Labeled</span><span class="metric-num" id="cnt_verified" style="color:var(--success);">{verified_count}</span></div>
            </div>

            <div class="project-bar">
                <div class="project-tabs" id="projectTabs"></div>
                <div style="display:flex; gap:6px;">
                    <button class="btn" onclick="openEditProjectModal()" style="font-size:12px;">⚙️ Edit Project</button>
                    <button class="btn btn-danger" onclick="deleteCurrentProject()" style="font-size:12px;">🗑️ Delete Project</button>
                </div>
            </div>

            <div class="class-distribution-bar">
                <div class="class-dist-header">
                    <span>🏷️ Filter Queue by Class Category:</span>
                    <span id="class_dist_ratio" style="color:var(--primary);">0% Verified</span>
                </div>
                <div class="class-chips-grid" id="classChipsGrid"></div>
            </div>

            <div class="status-filter-bar">
                <span style="font-size:11px; font-weight:800; color:var(--muted);">STATUS QUEUE:</span>
                <button id="flt_all" class="status-btn {'active' if status_filter == 'all' else ''}" onclick="switchStatusFilter('all')">
                    📋 All Items
                </button>
                <button id="flt_unverified" class="status-btn {'active' if status_filter == 'unverified' else ''}" onclick="switchStatusFilter('unverified')">
                    ⏳ Unverified / Incomplete
                </button>
                <button id="flt_verified" class="status-btn {'active' if status_filter == 'verified' else ''}" onclick="switchStatusFilter('verified')">
                    ✅ Verified / Completed
                </button>
            </div>

            <div id="focalContainer" class="focal-workspace">
                <div id="emptyWorkspaceMsg" class="empty-workspace-banner">No captures match selected filter combination.</div>
                
                <div id="activeWorkspaceCard" class="card-workspace-content">
                    <div class="media-box" id="mediaContainer">No Image</div>
                    <div class="info-box">
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span id="verifiedTag" style="font-size:11px; font-weight:800; color:var(--muted);">⏳ UNVERIFIED</span>
                                <div style="display:flex; gap:6px;">
                                    <button class="btn" onclick="unverifyCurrentItem()" style="padding:4px 8px; font-size:11px;" title="Reset verification status (Hotkey: U)">↩️ Reset Verification</button>
                                    <button class="btn" onclick="openEditItemModal()" style="padding:4px 8px; font-size:11px;">✏️ Edit</button>
                                    <button class="btn btn-danger" onclick="deleteCurrentItem()" style="padding:4px 8px; font-size:11px;">🗑️ Remove Item</button>
                                </div>
                            </div>
                            <h2 id="authorName" style="margin: 8px 0 6px 0; font-size: 18px;">Profile Name</h2>
                            <p style="font-size:12px; color:var(--muted); margin:2px 0;"><strong>Current Assigned Class:</strong> <span id="currentClassTag" style="color:var(--primary); font-weight:800;">Unassigned</span></p>
                            <p style="font-size:12px; color:var(--muted); margin:2px 0;"><strong>Monotonic Renamed Filename:</strong></p>
                            <div id="assignedFilenameBox" class="filename-box">Not yet renamed</div>
                            <p style="font-size:12px; color:var(--muted); margin:4px 0 2px 0;"><strong>Post Link:</strong> <a id="postLink" href="#" target="_blank" style="color:var(--primary);">Open Original Post ↗</a></p>
                            <p style="font-size:12px; color:var(--muted); margin:2px 0;"><strong>Privacy:</strong> <span id="privacyTag">-</span></p>
                        </div>

                        <div>
                            <label style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: UPPERCASE;">Assign / Change Custom Class Label (Hotkeys 1-9):</label>
                            <div class="class-picker" id="classPicker"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="nav-bar">
                <button class="btn" onclick="prevCard()">← Previous Item (←)</button>
                <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
                <span id="counterText" style="font-size:13px; font-weight:700; color:var(--muted);">0 / 0</span>
                <button class="btn btn-primary" onclick="nextCard()">Next Item (→)</button>
            </div>
        </div>

        <div class="modal-overlay" id="newProjectModal">
            <div class="modal-card">
                <h3>➕ Create New Dataset Project</h3>
                <div><label>Project Slug ID:</label><input type="text" id="np_slug" placeholder="e.g. crop_diseases_v1"/></div>
                <div><label>Project Title:</label><input type="text" id="np_title" placeholder="e.g. Agricultural Crop Leaf Classification"/></div>
                <div><label>Custom Classes (Comma-Separated):</label><input type="text" id="np_classes" placeholder="e.g. healthy, rust, blight, spot"/></div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <input type="checkbox" id="np_overwrite" style="width:auto;"/>
                    <label for="np_overwrite" style="font-size:12px; cursor:pointer;">Overwrite if Project ID already exists</label>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('newProjectModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitNewProject()">Create Project</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="editProjectModal">
            <div class="modal-card">
                <h3>⚙️ Edit Project Settings</h3>
                <div><label>Project Title:</label><input type="text" id="ep_title"/></div>
                <div><label>Custom Classes (Comma-Separated):</label><input type="text" id="ep_classes"/></div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('editProjectModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitEditProject()">Save Changes</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="importModal">
            <div class="modal-card">
                <h3>🔄 Sync & Fetch Stream Data</h3>
                <div>
                    <label>Select Sync Data Source:</label>
                    <select id="imp_source" onchange="togglePayloadBox(this.value)">
                        <option value="live">Sync from Active Live Logs</option>
                        <option value="history">Sync from Historical Log Archive</option>
                        <option value="combined">Sync from Both (Active + Archived)</option>
                        <option value="json_payload">Paste Raw Custom JSON Array</option>
                    </select>
                </div>
                <div id="payloadBox" style="display:none;">
                    <label>Raw JSON Array Payload:</label>
                    <textarea id="imp_payload" rows="5" placeholder='[{{"postUrl":"...", "profileName":"..."}}]'></textarea>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('importModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitImport()">Fetch & Sync Data</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="editItemModal">
            <div class="modal-card">
                <h3>✏️ Edit Item Metadata</h3>
                <div><label>Author Profile Name:</label><input type="text" id="ei_author"/></div>
                <div><label>Privacy Type:</label><input type="text" id="ei_privacy"/></div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('editItemModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitEditItem()">Update Item</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="exportModal">
            <div class="modal-card">
                <h3>📦 Export Dataset Archive</h3>
                <div>
                    <label>Choose Export Mode:</label>
                    <select id="exp_mode">
                        <option value="full">Full Archive (Bundled Media Images + JSON/CSV Manifests)</option>
                        <option value="metadata_only">Metadata Only (Fast CSV & JSON Manifest with Image Hyperlinks)</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('exportModal')">Cancel</button>
                    <button class="btn btn-success" onclick="triggerExportZip()">Download ZIP</button>
                </div>
            </div>
        </div>

        <script>
            const projects = {projects_json};
            const currentProject = {current_project_json};
            const allItems = {items_json};
            
            let activeStatusFilter = "{status_filter}";
            let activeClassFilter = "{class_filter}";
            
            let filteredItems = [];
            let currentIndex = 0;

            function normClass(cls) {{
                return (cls || "").toLowerCase().trim().replace(/[\s-]+/g, "_");
            }}

            function calculateClassDistribution() {{
                if (!currentProject || !currentProject.classes) return;

                const projClassesNorm = currentProject.classes.map(c => normClass(c));
                const counts = {{ unassigned: 0 }};
                projClassesNorm.forEach(c => counts[c] = 0);
                
                let total = allItems.length;
                let verified = 0;

                allItems.forEach(item => {{
                    if (item.isVerified) verified++;
                    const clsNorm = normClass(item.customClass);
                    if (clsNorm && projClassesNorm.includes(clsNorm)) {{
                        counts[clsNorm] = (counts[clsNorm] || 0) + 1;
                    }} else {{
                        counts.unassigned++;
                    }}
                }});

                const elTotal = document.getElementById('cnt_total');
                const elVer = document.getElementById('cnt_verified');
                const elUnver = document.getElementById('cnt_unverified');

                if (elTotal) elTotal.innerText = total;
                if (elVer) elVer.innerText = verified;
                if (elUnver) elUnver.innerText = total - verified;

                const ratio = total > 0 ? Math.round((verified / total) * 100) : 0;
                const elRatio = document.getElementById('class_dist_ratio');
                if (elRatio) elRatio.innerText = `${{ratio}}% Verified (${{verified}}/${{total}})`;

                const chipsContainer = document.getElementById('classChipsGrid');
                if (!chipsContainer) return;

                let html = `<div class="class-chip ${{activeClassFilter === 'all' ? 'active' : ''}}" onclick="switchClassFilter('all')">
                    📋 All Captures <span class="class-count-badge">${{total}}</span>
                </div>`;

                html += `<div class="class-chip unassigned-chip ${{activeClassFilter === 'unassigned' ? 'active' : ''}}" onclick="switchClassFilter('unassigned')">
                    ⚠️ Unassigned <span class="class-count-badge" style="background:#EF4444; color:#FFF;">${{counts.unassigned}}</span>
                </div>`;

                currentProject.classes.forEach(rawCls => {{
                    const clsNorm = normClass(rawCls);
                    const cnt = counts[clsNorm] || 0;
                    const isActive = (activeClassFilter === rawCls || activeClassFilter === clsNorm) ? 'active' : '';
                    html += `<div class="class-chip ${{isActive}}" onclick="switchClassFilter('${{rawCls}}')">
                        ${{rawCls}} <span class="class-count-badge">${{cnt}}</span>
                    </div>`;
                }});

                chipsContainer.innerHTML = html;
            }}

            function applyFilters() {{
                const projClassesNorm = currentProject ? currentProject.classes.map(c => normClass(c)) : [];
                const activeClassNorm = normClass(activeClassFilter);

                filteredItems = allItems.filter(i => {{
                    let passStatus = true;
                    if (activeStatusFilter === 'unverified') passStatus = !i.isVerified;
                    else if (activeStatusFilter === 'verified') passStatus = i.isVerified;

                    let passClass = true;
                    const itemClassNorm = normClass(i.customClass);

                    if (activeClassFilter === 'unassigned') {{
                        passClass = !itemClassNorm || !projClassesNorm.includes(itemClassNorm);
                    }} else if (activeClassFilter !== 'all') {{
                        passClass = (itemClassNorm === activeClassNorm);
                    }}

                    return passStatus && passClass;
                }});

                currentIndex = 0;
            }}

            function switchStatusFilter(status) {{
                activeStatusFilter = status;
                applyFilters();
                
                document.querySelectorAll('.status-btn').forEach(btn => btn.classList.remove('active'));
                const targetBtn = document.getElementById(`flt_${{status}}`);
                if (targetBtn) targetBtn.classList.add('active');
                
                renderCard();
            }}

            function switchClassFilter(cls) {{
                activeClassFilter = cls;
                calculateClassDistribution();
                applyFilters();
                renderCard();
            }}

            function getAdminKey() {{
                return sessionStorage.getItem("adminSecretKey") || document.getElementById("adminSecretKey").value;
            }}

            function saveAdminKey(val) {{
                sessionStorage.setItem("adminSecretKey", val);
                const el = document.getElementById("authStatus");
                if (el) el.innerText = val ? "✅ Session Authenticated" : "";
            }}

            window.onload = () => {{
                const savedKey = sessionStorage.getItem("adminSecretKey");
                if (savedKey) {{
                    const elKey = document.getElementById("adminSecretKey");
                    if (elKey) elKey.value = savedKey;
                    const elStat = document.getElementById("authStatus");
                    if (elStat) elStat.innerText = "✅ Session Authenticated";
                }}
            }};

            function showModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
            function hideModal(id) {{ document.getElementById(id).style.display = 'none'; }}
            function togglePayloadBox(val) {{ document.getElementById('payloadBox').style.display = val === 'json_payload' ? 'block' : 'none'; }}

            function renderTabs() {{
                const tabsBar = document.getElementById('projectTabs');
                if (!projects || projects.length === 0) {{
                    if (tabsBar) tabsBar.innerHTML = "<span style='color:var(--muted); font-size:13px;'>No Projects Found. Click 'New Project' to create one.</span>";
                    return;
                }}

                if (tabsBar) {{
                    tabsBar.innerHTML = projects.map(p => `
                        <div class="project-tab ${{currentProject && currentProject.projectId === p.projectId ? 'active' : ''}}"
                             onclick="window.location.href='/dataset-builder?project_id=${{p.projectId}}&status_filter=${{activeStatusFilter}}&class_filter=${{activeClassFilter}}'">
                            ${{p.title}} <small>(${{p.classes.join(', ')}})</small>
                        </div>
                    `).join('');
                }}
            }}

            function getResolvedImageUrl(item) {{
                if (!item) return "";
                if (item.assignedFilename) return `/media/images/${{item.assignedFilename}}`;
                if (item.imageUrl) {{
                    if (item.imageUrl.startsWith("http://") || item.imageUrl.startsWith("https://") || item.imageUrl.startsWith("/")) {{
                        return item.imageUrl;
                    }}
                    return `/media/images/${{item.imageUrl}}`;
                }}
                return "";
            }}

            function handleImageError(imgEl, rawUrl) {{
                if (rawUrl && !imgEl.dataset.triedFallback) {{
                    imgEl.dataset.triedFallback = "true";
                    const filename = rawUrl.split('/').pop();
                    imgEl.src = `/media/images/${{filename}}`;
                    return;
                }}
                imgEl.onerror = null;
                if (imgEl.parentElement) {{
                    imgEl.parentElement.innerHTML = "<span style='color:var(--danger); font-size:12px; font-weight:700;'>⚠️ Media Asset File Missing on Disk</span>";
                }}
            }}

            function safeSetText(id, text) {{
                const el = document.getElementById(id);
                if (el) el.innerText = text;
            }}

            function renderCard() {{
                const emptyBox = document.getElementById('emptyWorkspaceMsg');
                const cardBox = document.getElementById('activeWorkspaceCard');

                if (!filteredItems || filteredItems.length === 0) {{
                    if (cardBox) cardBox.style.display = 'none';
                    if (emptyBox) {{
                        emptyBox.style.display = 'block';
                        let emptyMsg = `No captures match combination [Class: ${{activeClassFilter.toUpperCase()}}] & [Status: ${{activeStatusFilter.toUpperCase()}}].`;
                        if (activeClassFilter === 'unassigned' && activeStatusFilter === 'unverified') {{
                            emptyMsg = "🎉 All captures in this project have been classed!";
                        }}
                        emptyBox.innerText = emptyMsg;
                    }}
                    safeSetText('counterText', "0 of 0");
                    const pFill = document.getElementById('progressFill');
                    if (pFill) pFill.style.width = "0%";
                    return;
                }}

                if (emptyBox) emptyBox.style.display = 'none';
                if (cardBox) cardBox.style.display = 'flex';

                if (currentIndex >= filteredItems.length) currentIndex = filteredItems.length - 1;
                if (currentIndex < 0) currentIndex = 0;

                const item = filteredItems[currentIndex];
                safeSetText('authorName', item.profileName || "Unknown Profile");
                safeSetText('currentClassTag', item.customClass ? item.customClass.toUpperCase() : "⚠️ UNASSIGNED");
                
                const tagEl = document.getElementById('currentClassTag');
                if (tagEl) tagEl.style.color = item.customClass ? "#60A5FA" : "#EF4444";

                const resolvedUrl = getResolvedImageUrl(item);
                safeSetText('assignedFilenameBox', item.assignedFilename || (resolvedUrl ? resolvedUrl.split('/').pop() : "unassigned"));
                
                const postLinkEl = document.getElementById('postLink');
                if (postLinkEl) postLinkEl.href = item.postUrl || "#";

                safeSetText('privacyTag', item.privacyType || "Unknown");
                safeSetText('verifiedTag', item.isVerified ? "✅ VERIFIED (COMPLETED)" : "⏳ UNVERIFIED");

                const vTagEl = document.getElementById('verifiedTag');
                if (vTagEl) vTagEl.style.color = item.isVerified ? "#10B981" : "#EF4444";

                safeSetText('counterText', `${{currentIndex + 1}} of ${{filteredItems.length}}`);
                
                const pFill = document.getElementById('progressFill');
                if (pFill) pFill.style.width = `${{((currentIndex + 1) / filteredItems.length) * 100}}%`;

                const mediaBox = document.getElementById('mediaContainer');
                if (mediaBox) {{
                    if (resolvedUrl) {{
                        mediaBox.innerHTML = `<img src="${{resolvedUrl}}" alt="Media Asset" onerror="handleImageError(this, '${{item.imageUrl || ''}}')"/>`;
                    }} else {{
                        mediaBox.innerHTML = "<span style='color:var(--muted); font-size:13px;'>No Media Asset</span>";
                    }}
                }}

                const picker = document.getElementById('classPicker');
                if (picker && currentProject && currentProject.classes) {{
                    picker.innerHTML = currentProject.classes.map((cls, idx) => `
                        <div class="cls-btn ${{normClass(item.customClass) === normClass(cls) ? 'active' : ''}}" onclick="assignClass('${{cls}}')">
                            ${{cls}} <small style="color:var(--muted);">[${{idx + 1}}]</small>
                        </div>
                    `).join('');
                }}
            }}

            function nextCard() {{ if (currentIndex < filteredItems.length - 1) {{ currentIndex++; renderCard(); }} }}
            function prevCard() {{ if (currentIndex > 0) {{ currentIndex--; renderCard(); }} }}

            document.addEventListener('keydown', (e) => {{
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
                if (e.key === 'ArrowRight') nextCard();
                if (e.key === 'ArrowLeft') prevCard();
                if (e.key === 'u' || e.key === 'U') unverifyCurrentItem();
                if (e.key === 'Delete' || e.key === 'Backspace') deleteCurrentItem();
                if (e.key >= '1' && e.key <= '9') {{
                    const idx = parseInt(e.key) - 1;
                    if (currentProject && currentProject.classes && currentProject.classes[idx]) {{
                        assignClass(currentProject.classes[idx]);
                    }}
                }}
            }});

            function assignClass(newClass) {{
                const key = getAdminKey();
                if (!key) {{ alert("Please enter your Session Admin Key above."); return; }}

                const item = filteredItems[currentIndex];
                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);
                formData.append('original_post_url', item.postUrl);
                formData.append('customClass', newClass);

                fetch('/api/v1/projects/update-item', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.updatedFields) {{
                        item.customClass = data.updatedFields.customClass || newClass;
                        item.isVerified = true;
                        if (data.updatedFields.assignedFilename) item.assignedFilename = data.updatedFields.assignedFilename;
                        if (data.updatedFields.imageUrl) item.imageUrl = data.updatedFields.imageUrl;
                    }}

                    calculateClassDistribution();

                    const newClassNorm = normClass(newClass);
                    const activeClassNorm = normClass(activeClassFilter);

                    if (activeClassFilter !== 'all' && activeClassNorm !== newClassNorm) {{
                        filteredItems.splice(currentIndex, 1);
                        renderCard();
                    }} else if (activeStatusFilter === 'unverified') {{
                        filteredItems.splice(currentIndex, 1);
                        renderCard();
                    }} else {{
                        renderCard();
                        nextCard();
                    }}
                }});
            }}

            function batchRenameClassified() {{
                if (!currentProject) return;
                const key = getAdminKey();
                if (!key) {{ alert("Please enter your Session Admin Key above."); return; }}

                if (!confirm(`Run batch renaming on existing classified captures in project '${{currentProject.title}}'?`)) return;

                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);

                fetch('/api/v1/projects/batch-rename', {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.detail) alert("Batch Rename Error: " + data.detail);
                    else {{
                        alert(`✅ Batch Renaming Complete: Renamed ${{data.renamed_count}} captures.`);
                        window.location.reload();
                    }}
                }})
                .catch(err => alert("Batch Rename Error: " + err));
            }}

            function unverifyCurrentItem() {{
                if (!filteredItems || filteredItems.length === 0 || !currentProject) return;
                const key = getAdminKey();
                if (!key) {{ alert("Please enter your Session Admin Key above."); return; }}

                const item = filteredItems[currentIndex];
                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);
                formData.append('original_post_url', item.postUrl);

                fetch('/api/v1/projects/unverify-item', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    item.isVerified = false;
                    calculateClassDistribution();

                    if (activeStatusFilter === 'verified') {{
                        filteredItems.splice(currentIndex, 1);
                        renderCard();
                    }} else {{
                        renderCard();
                    }}
                }});
            }}

            function deleteCurrentItem() {{
                if (!filteredItems || filteredItems.length === 0 || !currentProject) return;
                const item = filteredItems[currentIndex];
                if (!confirm(`Delete item '${{item.profileName}}' from dataset project?`)) return;

                const key = getAdminKey();
                fetch(`/api/v1/projects/delete-item?project_id=${{currentProject.projectId}}&post_url=${{encodeURIComponent(item.postUrl)}}`, {{
                    method: 'DELETE',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => {{
                    const mainIdx = allItems.findIndex(i => i.postUrl === item.postUrl);
                    if (mainIdx !== -1) allItems.splice(mainIdx, 1);

                    filteredItems.splice(currentIndex, 1);
                    if (currentIndex >= filteredItems.length && currentIndex > 0) currentIndex--;
                    
                    calculateClassDistribution();
                    renderCard();
                }});
            }}

            function submitNewProject() {{
                const key = getAdminKey();
                const slug = document.getElementById('np_slug').value;
                const title = document.getElementById('np_title').value;
                const classes = document.getElementById('np_classes').value;
                const overwrite = document.getElementById('np_overwrite').checked;

                if (!key || !slug || !title || !classes) {{ alert("All fields and Admin Key are required."); return; }}

                const formData = new FormData();
                formData.append('project_id', slug);
                formData.append('title', title);
                formData.append('classes', classes);
                formData.append('overwrite', overwrite);

                fetch('/api/v1/projects/create', {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.detail) alert(data.detail);
                    else window.location.href = `/dataset-builder?project_id=${{slug}}`;
                }});
            }}

            function openEditProjectModal() {{
                if (!currentProject) return;
                document.getElementById('ep_title').value = currentProject.title;
                document.getElementById('ep_classes').value = currentProject.classes.join(', ');
                showModal('editProjectModal');
            }}

            function submitEditProject() {{
                const key = getAdminKey();
                const title = document.getElementById('ep_title').value;
                const classes = document.getElementById('ep_classes').value;

                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);
                formData.append('title', title);
                formData.append('classes', classes);

                fetch('/api/v1/projects/update-settings', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => window.location.reload());
            }}

            function deleteCurrentProject() {{
                if (!currentProject) return;
                if (!confirm(`Are you sure you want to delete project '${{currentProject.title}}' and all its assigned items?`)) return;

                const key = getAdminKey();
                fetch(`/api/v1/projects/delete?project_id=${{currentProject.projectId}}`, {{
                    method: 'DELETE',
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.json())
                .then(data => window.location.href = '/dataset-builder');
            }}

            function submitImport() {{
                if (!currentProject) return;
                const key = getAdminKey();
                if (!key) {{
                    alert("🔒 Please enter your Session Admin Key in the top bar first!");
                    return;
                }}

                const source = document.getElementById('imp_source').value;
                const payload = document.getElementById('imp_payload').value;

                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);
                formData.append('source', source);
                if (source === 'json_payload') formData.append('raw_payload', payload);

                fetch('/api/v1/projects/import-external', {{
                    method: 'POST',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(async res => {{
                    if (!res.ok) {{
                        const errData = await res.json().catch(() => ({{ detail: "Import request failed." }}));
                        throw new Error(errData.detail || "Import error.");
                    }}
                    return res.json();
                }})
                .then(data => {{
                    hideModal('importModal');
                    const count = data.importedCount !== undefined ? data.importedCount : (data.imported_count || 0);
                    const src = data.source || data.source_type || source;
                    alert(`✅ Sync Complete: Imported ${{count}} new unclassed items from source '${{src}}'.`);
                    window.location.reload();
                }})
                .catch(err => {{
                    alert("❌ Sync Failed: " + err.message);
                }});
            }}

            function openEditItemModal() {{
                if (!filteredItems || filteredItems.length === 0) return;
                const item = filteredItems[currentIndex];
                document.getElementById('ei_author').value = item.profileName || '';
                document.getElementById('ei_privacy').value = item.privacyType || '';
                showModal('editItemModal');
            }}

            function submitEditItem() {{
                const key = getAdminKey();
                const item = filteredItems[currentIndex];
                const author = document.getElementById('ei_author').value;
                const privacy = document.getElementById('ei_privacy').value;

                const formData = new FormData();
                formData.append('project_id', currentProject.projectId);
                formData.append('original_post_url', item.postUrl);
                formData.append('profileName', author);
                formData.append('privacyType', privacy);

                fetch('/api/v1/projects/update-item', {{
                    method: 'PATCH',
                    headers: {{ 'X-Admin-Secret': key }},
                    body: formData
                }})
                .then(res => res.json())
                .then(data => {{
                    item.profileName = author;
                    item.privacyType = privacy;
                    hideModal('editItemModal');
                    renderCard();
                }});
            }}

            function triggerExportZip() {{
                if (!currentProject) return;
                const key = getAdminKey();
                if (!key) {{
                    alert("⚠️ Session Admin Key is missing. Please enter your secret key in the top bar.");
                    return;
                }}

                const mode = document.getElementById('exp_mode').value;
                hideModal('exportModal');

                fetch(`/api/v1/projects/export-zip?project_id=${{currentProject.projectId}}&mode=${{mode}}`, {{
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(async res => {{
                    if (!res.ok) {{
                        const errData = await res.json().catch(() => ({{ detail: "Export failed." }}));
                        throw new Error(errData.detail || "Export error occurred.");
                    }}
                    return res.blob();
                }})
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${{currentProject.projectId}}_${{mode}}_v{APP_VERSION}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }})
                .catch(err => {{
                    alert("❌ Download Failed: " + err.message);
                }});
            }}

            renderTabs();
            calculateClassDistribution();
            applyFilters();
            renderCard();
        </script>
    </body>
    </html>
    """