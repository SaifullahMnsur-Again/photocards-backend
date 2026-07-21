import os
import json
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.config import MEDIA_DIR
from app.db import collection, dataset_collection, projects_collection
from app.api.v1.analyze import router as analyze_router
from app.api.v1.dataset import router as dataset_router, build_advanced_mongo_query
from app.api.v1.history import router as history_router
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
# PAGE 1: LIVE LOGS STREAM DASHBOARD (/logs)
# ==============================================================================
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

    table_rows_html = ""
    if all_rows:
        for index, row in enumerate(all_rows, start=1):
            first_time = row.get("firstCapturedAt", row.get("capturedAt", ""))
            req_count = row.get("requestCount", 1)
            name = row.get("profileName", "Unknown Profile")
            pst_url = row.get("postUrl", "")
            priv = row.get("privacyType", "Unknown")
            img_url = row.get("imageUrl", "")
            stat = row.get("status", "low_confidence")

            table_rows_html += f"""
            <tr>
                <td><strong>#{index}</strong></td>
                <td><span style="background:rgba(59,130,246,0.2); color:#60A5FA; padding:2px 6px; border-radius:4px; font-weight:800;">×{req_count}</span></td>
                <td>{name}</td>
                <td><a href="{pst_url}" target="_blank" style="color:#3B82F6;">🔗 Post Link</a></td>
                <td>🔒 {priv}</td>
                <td>{stat}</td>
                <td><small style="color:#9CA3AF;">{first_time}</small></td>
                <td>{f'<a href="{img_url}" target="_blank" style="color:#10B981;">🖼️ Media</a>' if img_url else 'No Media'}</td>
            </tr>
            """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Live Logs — v{APP_VERSION}</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #090D16; color: #F9FAFB; padding: 24px; margin: 0; }}
            .container {{ max-width: 1300px; margin: 0 auto; }}
            .navbar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1F2937; padding-bottom: 16px; margin-bottom: 20px; }}
            .btn {{ background: #111827; border: 1px solid #1F2937; color: #FFF; padding: 8px 14px; border-radius: 8px; cursor: pointer; text-decoration: none; font-size: 13px; font-weight: 600; }}
            .btn-primary {{ background: #3B82F6; border-color: #3B82F6; }}
            table {{ width: 100%; border-collapse: collapse; background: #111827; border-radius: 10px; overflow: hidden; font-size: 13px; }}
            th, td {{ padding: 12px 16px; border-bottom: 1px solid #1F2937; text-align: left; }}
            th {{ background: #0F172A; color: #9CA3AF; font-size: 11px; text-transform: uppercase; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div>
                    <h1 style="margin:0; font-size:20px;">📊 Live Stream Index</h1>
                    <small style="color:#9CA3AF;">Engine v{APP_VERSION}</small>
                </div>
                <div>
                    <a href="/dataset-builder" class="btn btn-primary">🛠️ Open Dataset Studio</a>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>#</th><th>Reqs</th><th>Author</th><th>Post Link</th><th>Privacy</th><th>Status</th><th>First Seen</th><th>Media</th></tr>
                </thead>
                <tbody>{table_rows_html}</tbody>
            </table>
        </div>
    </body>
    </html>
    """


# ==============================================================================
# PAGE 2: MULTI-PROJECT DATASET STUDIO (/dataset-builder)
# ==============================================================================
@app.get("/dataset-builder", response_class=HTMLResponse)
async def view_dataset_builder(project_id: Optional[str] = Query(None)):
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

    total_items_count = len(items)
    verified_count = len([i for i in items if i.get("isVerified")])

    projects_json = json.dumps(projects)
    items_json = json.dumps(items)
    current_project_json = json.dumps(current_project) if current_project else "null"

    active_project_title = current_project["projectId"] if current_project else "No Active Project"
    active_classes_str = ", ".join(current_project["classes"]) if current_project else "None"

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
                --success: #10B981; --danger: #EF4444;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
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

            .metrics-bar {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
            .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }}
            .metric-title {{ font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 700; }}
            .metric-num {{ font-size: 20px; font-weight: 800; }}

            .project-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; gap: 12px; }}
            .project-tabs {{ display: flex; gap: 10px; overflow-x: auto; }}
            .project-tab {{ background: var(--panel); border: 1px solid var(--border); padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; white-space: nowrap; }}
            .project-tab.active {{ background: var(--primary); border-color: var(--primary); color: white; }}

            .focal-workspace {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 28px; display: flex; gap: 28px; align-items: center; min-height: 400px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }}
            .media-box {{ flex: 1; height: 360px; background: #000; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border); position: relative; }}
            .media-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
            .info-box {{ flex: 1; display: flex; flex-direction: column; gap: 16px; justify-content: space-between; height: 360px; }}

            .class-picker {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; margin-top: 10px; }}
            .cls-btn {{ padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: #1F2937; color: var(--text); font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; text-transform: capitalize; transition: all 0.15s ease; }}
            .cls-btn:hover {{ border-color: var(--primary); transform: translateY(-1px); }}
            .cls-btn.active {{ border-color: var(--primary); background: rgba(59, 130, 246, 0.2); color: #60A5FA; }}

            .nav-bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }}
            .progress-bar {{ flex: 1; height: 6px; background: var(--border); border-radius: 3px; margin: 0 20px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: var(--success); width: 0%; transition: width 0.3s ease; }}

            /* Modals */
            .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(4px); }}
            .modal-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; width: 440px; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
            .modal-card h3 {{ margin: 0; font-size: 16px; font-weight: 700; }}
            .modal-card label {{ font-size: 12px; font-weight: 600; color: var(--muted); }}
            .modal-card input, .modal-card textarea, .modal-card select {{ background: var(--bg); border: 1px solid var(--border); color: #FFF; padding: 10px; border-radius: 8px; font-size: 13px; outline: none; width: 100%; box-sizing: border-box; }}
            .modal-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="navbar">
                <div class="brand">
                    <h1>🛠️ Dataset Studio <small style="font-size:12px; color:var(--muted);">v{APP_VERSION}</small></h1>
                </div>
                <div class="controls">
                    <a href="/logs" class="btn">← Live Stream</a>
                    <button class="btn btn-primary" onclick="showModal('newProjectModal')">➕ New Project</button>
                    <button class="btn" onclick="showModal('importModal')">📥 Import Items</button>
                    <button class="btn btn-success" onclick="exportProjectZip()">📦 Export ZIP</button>
                </div>
            </div>

            <!-- Persistent Auth Bar -->
            <div class="auth-bar">
                <span style="font-size:12px; font-weight:700; color:var(--muted);">🔒 SESSION ADMIN KEY:</span>
                <input type="password" id="adminSecretKey" placeholder="Enter key once..." onchange="saveAdminKey(this.value)"/>
                <span id="authStatus" style="font-size:12px; font-weight:700; color:var(--muted);"></span>
            </div>

            <div class="metrics-bar">
                <div class="metric-card"><span class="metric-title">Project Items</span><span class="metric-num">{total_items_count}</span></div>
                <div class="metric-card"><span class="metric-title">Verified Items</span><span class="metric-num" style="color:var(--success);">{verified_count}</span></div>
                <div class="metric-card"><span class="metric-title">Active Schema</span><span class="metric-num" style="font-size:14px; color:var(--primary);">{active_project_title}</span></div>
                <div class="metric-card"><span class="metric-title">Defined Classes</span><span class="metric-num" style="font-size:14px; color:#A7F3D0;">{active_classes_str}</span></div>
            </div>

            <div class="project-bar">
                <div class="project-tabs" id="projectTabs"></div>
                <div style="display:flex; gap:6px;">
                    <button class="btn" onclick="openEditProjectModal()" style="font-size:12px;">⚙️ Edit Project</button>
                    <button class="btn btn-danger" onclick="deleteCurrentProject()" style="font-size:12px;">🗑️ Delete Project</button>
                </div>
            </div>

            <div id="focalContainer" class="focal-workspace">
                <div class="media-box" id="mediaContainer">No Image</div>
                <div class="info-box">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span id="verifiedTag" style="font-size:11px; font-weight:800; color:var(--muted);">⏳ UNVERIFIED</span>
                            <button class="btn" onclick="openEditItemModal()" style="padding:4px 8px; font-size:11px;">✏️ Edit Metadata</button>
                        </div>
                        <h2 id="authorName" style="margin: 8px 0 6px 0; font-size: 18px;">Profile Name</h2>
                        <p style="font-size:12px; color:var(--muted); margin:2px 0;"><strong>Post Link:</strong> <a id="postLink" href="#" target="_blank" style="color:var(--primary);">Open Original Post ↗</a></p>
                        <p style="font-size:12px; color:var(--muted); margin:2px 0;"><strong>Privacy:</strong> <span id="privacyTag">-</span></p>
                    </div>

                    <div>
                        <label style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: UPPERCASE;">Assign Custom Class Label (Use hotkeys 1-9):</label>
                        <div class="class-picker" id="classPicker"></div>
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

        <!-- MODAL 1: CREATE PROJECT -->
        <div class="modal-overlay" id="newProjectModal">
            <div class="modal-card">
                <h3>➕ Create New Dataset Project</h3>
                <div>
                    <label>Project Slug ID:</label>
                    <input type="text" id="np_slug" placeholder="e.g. crop_diseases_v1"/>
                </div>
                <div>
                    <label>Project Title:</label>
                    <input type="text" id="np_title" placeholder="e.g. Agricultural Crop Leaf Classification"/>
                </div>
                <div>
                    <label>Custom Classes (Comma-Separated):</label>
                    <input type="text" id="np_classes" placeholder="e.g. healthy, rust, blight, spot"/>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('newProjectModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitNewProject()">Create Project</button>
                </div>
            </div>
        </div>

        <!-- MODAL 2: EDIT PROJECT SETTINGS -->
        <div class="modal-overlay" id="editProjectModal">
            <div class="modal-card">
                <h3>⚙️ Edit Project Settings</h3>
                <div>
                    <label>Project Title:</label>
                    <input type="text" id="ep_title"/>
                </div>
                <div>
                    <label>Custom Classes (Comma-Separated):</label>
                    <input type="text" id="ep_classes"/>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('editProjectModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitEditProject()">Save Changes</button>
                </div>
            </div>
        </div>

        <!-- MODAL 3: IMPORT ITEMS -->
        <div class="modal-overlay" id="importModal">
            <div class="modal-card">
                <h3>📥 Universal Import Engine</h3>
                <div>
                    <label>Select Import Source:</label>
                    <select id="imp_source" onchange="togglePayloadBox(this.value)">
                        <option value="live">Active Live Logs</option>
                        <option value="history">Historical Log Archive</option>
                        <option value="json_payload">Paste Raw JSON Array</option>
                    </select>
                </div>
                <div id="payloadBox" style="display:none;">
                    <label>Raw JSON Array Payload:</label>
                    <textarea id="imp_payload" rows="5" placeholder='[{{"postUrl":"...", "profileName":"..."}}]'></textarea>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('importModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitImport()">Import Items</button>
                </div>
            </div>
        </div>

        <!-- MODAL 4: EDIT ITEM METADATA -->
        <div class="modal-overlay" id="editItemModal">
            <div class="modal-card">
                <h3>✏️ Edit Item Metadata</h3>
                <div>
                    <label>Author Profile Name:</label>
                    <input type="text" id="ei_author"/>
                </div>
                <div>
                    <label>Privacy Type:</label>
                    <input type="text" id="ei_privacy"/>
                </div>
                <div class="modal-actions">
                    <button class="btn" onclick="hideModal('editItemModal')">Cancel</button>
                    <button class="btn btn-primary" onclick="submitEditItem()">Update Item</button>
                </div>
            </div>
        </div>

        <script>
            const projects = {projects_json};
            const currentProject = {current_project_json};
            const items = {items_json};
            let currentIndex = 0;

            function getAdminKey() {{
                return sessionStorage.getItem("adminSecretKey") || document.getElementById("adminSecretKey").value;
            }}

            function saveAdminKey(val) {{
                sessionStorage.setItem("adminSecretKey", val);
                document.getElementById("authStatus").innerText = val ? "✅ Session Authenticated" : "";
            }}

            window.onload = () => {{
                const savedKey = sessionStorage.getItem("adminSecretKey");
                if (savedKey) {{
                    document.getElementById("adminSecretKey").value = savedKey;
                    document.getElementById("authStatus").innerText = "✅ Session Authenticated";
                }}
            }};

            function showModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
            function hideModal(id) {{ document.getElementById(id).style.display = 'none'; }}
            function togglePayloadBox(val) {{ document.getElementById('payloadBox').style.display = val === 'json_payload' ? 'block' : 'none'; }}

            function renderTabs() {{
                const tabsBar = document.getElementById('projectTabs');
                if (!projects || projects.length === 0) {{
                    tabsBar.innerHTML = "<span style='color:var(--muted); font-size:13px;'>No Projects Found. Click 'New Project' to create one.</span>";
                    return;
                }}

                tabsBar.innerHTML = projects.map(p => `
                    <div class="project-tab ${{currentProject && currentProject.projectId === p.projectId ? 'active' : ''}}"
                         onclick="window.location.href='/dataset-builder?project_id=${{p.projectId}}'">
                        ${{p.title}} <small>(${{p.classes.join(', ')}})</small>
                    </div>
                `).join('');
            }}

            function renderCard() {{
                if (!items || items.length === 0) {{
                    document.getElementById('focalContainer').innerHTML = "<div style='text-align:center; width:100%; color:var(--muted); padding:40px;'>Project is empty. Click 'Import Items' to populate.</div>";
                    return;
                }}

                const item = items[currentIndex];
                document.getElementById('authorName').innerText = item.profileName || "Unknown Profile";
                document.getElementById('postLink').href = item.postUrl || "#";
                document.getElementById('privacyTag').innerText = item.privacyType || "Unknown";
                document.getElementById('verifiedTag').innerText = item.isVerified ? "✅ VERIFIED" : "⏳ UNVERIFIED";
                document.getElementById('verifiedTag').style.color = item.isVerified ? "#10B981" : "#9CA3AF";

                document.getElementById('counterText').innerText = `${{currentIndex + 1}} of ${{items.length}}`;
                document.getElementById('progressFill').style.width = `${{((currentIndex + 1) / items.length) * 100}}%`;

                const mediaBox = document.getElementById('mediaContainer');
                if (item.imageUrl) {{
                    mediaBox.innerHTML = `<img src="${{item.imageUrl}}" alt="Media Asset"/>`;
                }} else {{
                    mediaBox.innerHTML = "<span style='color:var(--muted); font-size:13px;'>No Media Asset</span>";
                }}

                const picker = document.getElementById('classPicker');
                if (currentProject && currentProject.classes) {{
                    picker.innerHTML = currentProject.classes.map((cls, idx) => `
                        <div class="cls-btn ${{item.customClass === cls ? 'active' : ''}}" onclick="assignClass('${{cls}}')">
                            ${{cls}} <small style="color:var(--muted);">[${{idx + 1}}]</small>
                        </div>
                    `).join('');
                }}
            }}

            function nextCard() {{ if (currentIndex < items.length - 1) {{ currentIndex++; renderCard(); }} }}
            function prevCard() {{ if (currentIndex > 0) {{ currentIndex--; renderCard(); }} }}

            document.addEventListener('keydown', (e) => {{
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
                if (e.key === 'ArrowRight') nextCard();
                if (e.key === 'ArrowLeft') prevCard();
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

                const item = items[currentIndex];
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
                    item.customClass = newClass;
                    item.isVerified = true;
                    renderCard();
                    nextCard();
                }});
            }}

            function submitNewProject() {{
                const key = getAdminKey();
                const slug = document.getElementById('np_slug').value;
                const title = document.getElementById('np_title').value;
                const classes = document.getElementById('np_classes').value;

                if (!key || !slug || !title || !classes) {{ alert("All fields and Admin Key are required."); return; }}

                const formData = new FormData();
                formData.append('project_id', slug);
                formData.append('title', title);
                formData.append('classes', classes);

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
                .then(res => res.json())
                .then(data => {{
                    hideModal('importModal');
                    window.location.reload();
                }});
            }}

            function openEditItemModal() {{
                if (!items || items.length === 0) return;
                const item = items[currentIndex];
                document.getElementById('ei_author').value = item.profileName || '';
                document.getElementById('ei_privacy').value = item.privacyType || '';
                showModal('editItemModal');
            }}

            function submitEditItem() {{
                const key = getAdminKey();
                const item = items[currentIndex];
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

            function exportProjectZip() {{
                if (!currentProject) return;
                const key = getAdminKey();

                fetch(`/api/v1/projects/export-zip?project_id=${{currentProject.projectId}}`, {{
                    headers: {{ 'X-Admin-Secret': key }}
                }})
                .then(res => res.blob())
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${{currentProject.projectId}}_v{APP_VERSION}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }});
            }}

            renderTabs();
            renderCard();
        </script>
    </body>
    </html>
    """