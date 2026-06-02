// API Connector — Admin Dashboard Application State

const API_BASE = "/api/v1";
let currentTab = "overview";
let currentConnections = [];

// =====================================================================
// INIT & BOOTSTRAP
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
    // Render initial icons
    lucide.createIcons();
    
    // Fetch and populate initial screen data
    refreshAll();

    // Setup visual event listeners for category maps
    loadCategoryDefaults();

    // Auto-update cURL commands in explorer
    updateExplorerTip();

    // Watch explorer key input for cURL preview updates
    const explorerKeyInput = document.getElementById("explorer-api-key");
    if (explorerKeyInput) explorerKeyInput.addEventListener("input", updateExplorerTip);
});

// Refresh all sections from DB
async function refreshAll() {
    toggleRefreshIcon(true);
    await Promise.all([
        fetchAnalytics(),
        fetchConnections(),
        fetchKeys()
    ]);
    toggleRefreshIcon(false);
}

function toggleRefreshIcon(spinning) {
    const icon = document.getElementById("global-refresh-icon");
    if (icon) {
        if (spinning) {
            icon.classList.add("rotate");
        } else {
            icon.classList.remove("rotate");
        }
    }
}

// =====================================================================
// NAVIGATION CONTROLLERS
// =====================================================================
function switchTab(tabId) {
    currentTab = tabId;
    
    // Toggle active menu button state
    document.querySelectorAll(".nav-menu .nav-btn").forEach(btn => {
        btn.classList.remove("active");
    });
    
    const activeBtn = document.getElementById(`btn-${tabId}`);
    if (activeBtn) activeBtn.classList.add("active");

    // Toggle active section visibility
    document.querySelectorAll(".content-body .tab-content").forEach(sec => {
        sec.classList.remove("active");
    });
    
    const activeSec = document.getElementById(`sec-${tabId}`);
    if (activeSec) activeSec.classList.add("active");

    // Update Top bar titles
    const titles = {
        "overview": { title: "Dashboard Overview", subtitle: "Real-time status, cache counters, and active integrations." },
        "connections": { title: "API Connections", subtitle: "Register and map third-party endpoints into standard schemas." },
        "keys": { title: "Secure Access Keys", subtitle: "Manage API keys to grant external apps access to the unified endpoints." },
        "explorer": { title: "Unified Gateway Explorer", subtitle: "Test secure aggregated feeds, verify normalized payloads, and retrieve integrations code." }
    };

    if (titles[tabId]) {
        document.getElementById("current-section-title").innerText = titles[tabId].title;
        document.getElementById("current-section-subtitle").innerText = titles[tabId].subtitle;
    }

    // Secondary fetch hooks for smooth rendering
    if (tabId === "overview") fetchAnalytics();
    else if (tabId === "connections") fetchConnections();
    else if (tabId === "keys") fetchKeys();
    
    lucide.createIcons();
}

// =====================================================================
// OVERVIEW & ANALYTICS LOADER
// =====================================================================
async function fetchAnalytics() {
    try {
        const response = await fetch(`${API_BASE}/analytics`);
        if (!response.ok) throw new Error("Failed to load analytics");
        
        const data = await response.json();
        
        // Update metric values
        document.getElementById("stat-total-conn").innerText = data.connections_summary.total;
        document.getElementById("stat-active-conn").innerText = `${data.connections_summary.active} Active`;
        document.getElementById("stat-inactive-conn").innerText = `${data.connections_summary.inactive} Inactive`;
        
        const totalCache = data.cache.total_queries;
        const cachePercent = totalCache > 0 ? Math.round((data.cache.hits / totalCache) * 100) : 0;
        document.getElementById("stat-cache-ratio").innerText = `${cachePercent}%`;
        document.getElementById("stat-cache-hits").innerText = `${data.cache.hits} Hits`;
        document.getElementById("stat-cache-misses").innerText = `${data.cache.misses} Misses`;

        // Calculate average system response latency
        const keys = Object.keys(data.performance);
        const avgTotalLat = keys.length > 0 
            ? Math.round(keys.reduce((acc, k) => acc + data.performance[k].avg_latency_ms, 0) / keys.length)
            : 0;
        document.getElementById("stat-avg-latency").innerText = `${avgTotalLat}ms`;

        // Render latency performance listing
        const perfContainer = document.getElementById("performance-list");
        if (keys.length === 0) {
            perfContainer.innerHTML = `<div class="no-data">No active integrations measured yet.</div>`;
        } else {
            perfContainer.innerHTML = keys.map(k => {
                const item = data.performance[k];
                const latencyColor = item.avg_latency_ms > 500 ? "var(--coral)" : "var(--teal)";
                const catBadge = item.category === "jobs" ? "badge-info" : (item.category === "courses" ? "badge-success" : "badge-warning");
                
                return `
                    <div class="perf-item animate-fade-in">
                        <div class="perf-info">
                            <h4>${k}</h4>
                            <span class="badge ${catBadge}">${item.category.toUpperCase()}</span>
                        </div>
                        <div class="perf-metrics">
                            <div class="perf-latency" style="color: ${latencyColor}">${item.avg_latency_ms}ms</div>
                            <div class="perf-rate">${item.success_rate}% success</div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        // Render Activity Logs table
        const logsContainer = document.getElementById("logs-table-body");
        document.getElementById("logs-count").innerText = `${data.recent_logs.length} Records`;
        
        if (data.recent_logs.length === 0) {
            logsContainer.innerHTML = `<tr><td colspan="4" class="text-center muted-text">No activity logged. Trigger some API connections!</td></tr>`;
        } else {
            logsContainer.innerHTML = data.recent_logs.map(log => {
                const statusBadge = log.status === "success" ? "badge-success" : "badge-danger";
                const dateStr = new Date(log.timestamp).toLocaleTimeString();
                
                return `
                    <tr>
                        <td><strong>${log.connection_name}</strong></td>
                        <td><span class="badge ${statusBadge}">${log.response_status} ${log.status.toUpperCase()}</span></td>
                        <td class="font-mono">${log.response_time_ms}ms</td>
                        <td class="muted-text">${dateStr}</td>
                    </tr>
                `;
            }).join("");
        }
        
        lucide.createIcons();
    } catch (e) {
        showToast("Error retrieving gateway analytics stats: " + e.message, "danger");
    }
}

// =====================================================================
// INTEGRATIONS & CONNECTION MANAGER (CRUD)
// =====================================================================
async function fetchConnections() {
    try {
        const response = await fetch(`${API_BASE}/connections`);
        if (!response.ok) throw new Error("Failed to load connections list");
        
        currentConnections = await response.json();
        const grid = document.getElementById("connections-grid-container");
        
        if (currentConnections.length === 0) {
            grid.innerHTML = `<div class="no-data">No connections registered. Use the builder wizard to add your first API!</div>`;
            return;
        }

        grid.innerHTML = currentConnections.map(conn => {
            const catBadge = conn.category === "jobs" ? "badge-info" : (conn.category === "courses" ? "badge-success" : "badge-warning");
            const activeChecked = conn.is_active ? "checked" : "";
            
            return `
                <div class="conn-card animate-fade-in" id="conn-card-${conn.id}">
                    <div class="conn-card-header">
                        <div class="conn-title-group">
                            <h4>${conn.name}</h4>
                            <span class="badge ${catBadge}">${conn.category.toUpperCase()}</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" ${activeChecked} onchange="toggleConnectionActive(${conn.id}, this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    <div class="conn-card-body">
                        <div class="conn-url-box" title="${conn.url}">${conn.url}</div>
                        <div class="conn-meta-row">
                            <div class="conn-meta-item">
                                <i data-lucide="clock"></i>
                                <span>Cache TTL: ${conn.cache_ttl}s</span>
                            </div>
                            <div class="conn-meta-item">
                                <i data-lucide="split"></i>
                                <span>Selector: <code>${conn.payload_selector || "Root"}</code></span>
                            </div>
                        </div>
                    </div>
                    <div class="conn-card-actions">
                        <button class="btn btn-secondary btn-icon-only" onclick="editConnection(${conn.id})" title="Edit Settings">
                            <i data-lucide="edit"></i>
                        </button>
                        <button class="btn btn-info btn-icon-only" onclick="testConnectionFromGrid(${conn.id})" title="Test Live Payload Mapping">
                            <i data-lucide="play"></i>
                        </button>
                        <button class="btn btn-danger btn-icon-only" onclick="deleteConnection(${conn.id})" title="Revoke Integration">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join("");
        
        lucide.createIcons();
    } catch (e) {
        showToast("Error getting integrations: " + e.message, "danger");
    }
}

async function toggleConnectionActive(id, isActive) {
    try {
        const response = await fetch(`${API_BASE}/connections/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: isActive })
        });
        
        if (!response.ok) throw new Error("Toggle status update failed");
        showToast(`Source successfully ${isActive ? 'activated' : 'deactivated'}.`, "success");
        fetchAnalytics();
    } catch (e) {
        showToast("Error toggling: " + e.message, "danger");
    }
}

async function deleteConnection(id) {
    showConfirm(
        "Delete Integration?",
        "This will permanently remove this API connection and invalidate its cache. This cannot be undone.",
        "Delete Connection",
        async () => {
            try {
                const response = await fetch(`${API_BASE}/connections/${id}`, {
                    method: "DELETE"
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                showToast("Connection successfully deleted.", "success");
                refreshAll();
            } catch (e) {
                showToast("Error deleting connection: " + e.message, "danger");
            }
        }
    );
}

// =====================================================================
// CONNECTION BUILDER WIZARD (FORM DIALOG)
// =====================================================================
function openWizard(connId = null) {
    const modal = document.getElementById("connection-wizard-modal");
    const form = document.getElementById("connection-form");
    
    // Clear and reset form
    form.reset();
    document.getElementById("form-conn-id").value = "";
    document.getElementById("wizard-modal-title").innerText = "New Integration Connection";
    document.getElementById("btn-save-conn").innerText = "Save Connection";
    document.getElementById("btn-test-mapping").classList.add("hide"); // Hide live tester on initial new connection creation
    
    // Reset test console
    document.getElementById("raw-response-preview").innerText = 'Click "Test Mapping" to fetch live data...';
    document.getElementById("normalized-response-preview").innerText = 'Fields will map here based on mapping JSON rules...';
    document.getElementById("test-latency-badge").classList.add("hide");

    if (connId) {
        const conn = currentConnections.find(c => c.id === connId);
        if (conn) {
            document.getElementById("form-conn-id").value = conn.id;
            document.getElementById("conn-name").value = conn.name;
            document.getElementById("conn-category").value = conn.category;
            document.getElementById("conn-url").value = conn.url;
            document.getElementById("conn-method").value = conn.method;
            document.getElementById("conn-ttl").value = conn.cache_ttl;
            document.getElementById("conn-selector").value = conn.payload_selector;
            document.getElementById("conn-headers").value = conn.headers;
            document.getElementById("conn-params").value = conn.params;
            document.getElementById("conn-mapping").value = conn.field_mapping;
            
            document.getElementById("wizard-modal-title").innerText = `Configure — ${conn.name}`;
            document.getElementById("btn-save-conn").innerText = "Update Connection";
            document.getElementById("btn-test-mapping").classList.remove("hide"); // Enable testing on existing configs
        }
    }

    loadCategoryDefaults();
    modal.classList.add("show");
    lucide.createIcons();
}

// Close builder dialog
function closeWizard() {
    document.getElementById("connection-wizard-modal").classList.remove("show");
}

function editConnection(id) {
    openWizard(id);
}

function loadCategoryDefaults() {
    const category = document.getElementById("conn-category").value;
    const mappingTextarea = document.getElementById("conn-mapping");
    const fieldsHint = document.getElementById("mapping-fields-hint");

    const defaultMappings = {
        "jobs": {
            "template": {
                "id": "job_id",
                "title": "job_title",
                "company": "organization.name",
                "location": "work_location",
                "description": "role_description",
                "url": "apply_url",
                "salary": "annual_compensation",
                "tags": "tags_list",
                "posted_at": "date_posted"
            },
            "hints": ["id (req)", "title (req)", "company (req)", "location (req)", "description (req)", "url (req)", "salary", "tags", "posted_at"]
        },
        "courses": {
            "template": {
                "id": "id",
                "title": "name",
                "provider": "academy",
                "instructor": "tutor",
                "description": "summary",
                "url": "link",
                "price": "cost",
                "duration": "length",
                "rating": "rating_stars"
            },
            "hints": ["id (req)", "title (req)", "provider (req)", "instructor (req)", "description (req)", "url (req)", "price", "duration", "rating"]
        },
        "events": {
            "template": {
                "id": "event_code",
                "title": "event_title",
                "organizer": "host_org",
                "venue": "location_name",
                "description": "details",
                "url": "register_link",
                "date": "start_date",
                "price": "ticket_price"
            },
            "hints": ["id (req)", "title (req)", "organizer (req)", "venue (req)", "description (req)", "url (req)", "date (req)", "price"]
        }
    };

    const sel = defaultMappings[category];
    
    // Only prefill mapping textarea if it is completely empty
    if (!mappingTextarea.value || mappingTextarea.value.trim() === "{}") {
        mappingTextarea.value = JSON.stringify(sel.template, null, 2);
    }

    // Populate Visual hints badges
    fieldsHint.innerHTML = sel.hints.map(field => {
        const isRequired = field.includes("(req)");
        const className = isRequired ? "field-tag required" : "field-tag";
        return `<span class="${className}">${field.replace(" (req)", "")}</span>`;
    }).join("");
}

// Save connection from wizard form
async function saveConnection(event) {
    event.preventDefault();
    
    const connId = document.getElementById("form-conn-id").value;
    const isEdit = connId !== "";
    
    // Build payload
    const connData = {
        name: document.getElementById("conn-name").value,
        category: document.getElementById("conn-category").value,
        url: document.getElementById("conn-url").value,
        method: document.getElementById("conn-method").value,
        cache_ttl: parseInt(document.getElementById("conn-ttl").value) || 300,
        payload_selector: document.getElementById("conn-selector").value || "",
        headers: document.getElementById("conn-headers").value || "{}",
        params: document.getElementById("conn-params").value || "{}",
        field_mapping: document.getElementById("conn-mapping").value || "{}"
    };

    // Minor validations
    try {
        if (connData.headers) JSON.parse(connData.headers);
        if (connData.params) JSON.parse(connData.params);
        if (connData.field_mapping) JSON.parse(connData.field_mapping);
    } catch (e) {
        showToast("Invalid JSON syntax inside parameter panels: " + e.message, "danger");
        return;
    }

    try {
        let response;
        if (isEdit) {
            response = await fetch(`${API_BASE}/connections/${connId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(connData)
            });
        } else {
            response = await fetch(`${API_BASE}/connections`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(connData)
            });
        }

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Request failed");
        }

        showToast(`Connection configuration successfully ${isEdit ? 'updated' : 'registered'}.`, "success");
        closeWizard();
        refreshAll();
    } catch (e) {
        showToast("Error saving connection: " + e.message, "danger");
    }
}

// Live Mapping Test Pipeline inside the wizard modal
async function runLiveMappingTest() {
    const connId = document.getElementById("form-conn-id").value;
    if (!connId) {
        showToast("Please save this connection first before running a visual mapper test.", "warning");
        return;
    }

    const testBtn = document.getElementById("btn-test-mapping");
    const rawPreview = document.getElementById("raw-response-preview");
    const normalizedPreview = document.getElementById("normalized-response-preview");
    const latencyBadge = document.getElementById("test-latency-badge");

    testBtn.disabled = true;
    testBtn.innerHTML = `<i data-lucide="refresh-cw" class="rotate small-icon"></i> Testing...`;
    lucide.createIcons();

    rawPreview.innerText = "Fetching live payload...";
    normalizedPreview.innerText = "Translating fields...";
    latencyBadge.classList.add("hide");

    try {
        // Save current form settings first so the database is updated with the field_mapping rules
        const connData = {
            name: document.getElementById("conn-name").value,
            category: document.getElementById("conn-category").value,
            url: document.getElementById("conn-url").value,
            method: document.getElementById("conn-method").value,
            cache_ttl: parseInt(document.getElementById("conn-ttl").value) || 300,
            payload_selector: document.getElementById("conn-selector").value || "",
            headers: document.getElementById("conn-headers").value || "{}",
            params: document.getElementById("conn-params").value || "{}",
            field_mapping: document.getElementById("conn-mapping").value || "{}"
        };

        const updateRes = await fetch(`${API_BASE}/connections/${connId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(connData)
        });
        if (!updateRes.ok) throw new Error("Auto-save configuration before test failed.");

        // Call the test connection runner
        const response = await fetch(`${API_BASE}/connections/${connId}/test`, {
            method: "POST"
        });
        if (!response.ok) throw new Error("HTTP connection check failed");

        const data = await response.json();
        
        if (data.status === "success") {
            rawPreview.innerText = JSON.stringify(data.raw_payload_preview, null, 2);
            normalizedPreview.innerText = JSON.stringify(data.normalized_data_preview, null, 2);
            
            latencyBadge.innerText = `${Math.round(data.latency_ms)}ms Latency`;
            latencyBadge.className = "badge badge-success animate-fade-in";
            showToast("Visual mapping run complete.", "success");
        } else {
            rawPreview.innerText = "FETCH FAILED";
            normalizedPreview.innerText = "Error details:\n" + data.error_message;
            latencyBadge.innerText = "Failed";
            latencyBadge.className = "badge badge-danger";
            showToast("Mapping test failed: " + data.error_message, "danger");
        }
    } catch (e) {
        rawPreview.innerText = "ERROR OCCURRED";
        normalizedPreview.innerText = e.message;
        latencyBadge.innerText = "Error";
        latencyBadge.className = "badge badge-danger";
        showToast("Error running test: " + e.message, "danger");
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = `<i data-lucide="play"></i> Test Mapping`;
        lucide.createIcons();
    }
}

// Redirects grids play button to the wizard with live tests pre-triggered
function testConnectionFromGrid(id) {
    openWizard(id);
    // Give wizard a slight moment to mount and transition CSS before triggering
    setTimeout(() => {
        runLiveMappingTest();
    }, 450);
}

// =====================================================================
// ACCESS KEYS CONTROLLERS
// =====================================================================
async function fetchKeys() {
    try {
        const response = await fetch(`${API_BASE}/keys`);
        if (!response.ok) throw new Error("Failed to load active keys");
        
        const keys = await response.json();
        
        // Update top-bar key indicators
        document.getElementById("active-keys-count").innerText = `${keys.length} Keys Active`;

        const tbody = document.getElementById("keys-table-body");
        if (keys.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center muted-text">No API keys registered. Create a key to secure your gateways!</td></tr>`;
            return;
        }

        tbody.innerHTML = keys.map(k => {
            const dateStr = new Date(k.created_at).toLocaleDateString();
            const hashPreview = k.key_hash ? `SHA256...${k.key_hash.substring(0, 16)}` : "SHA256...[hidden]";
            return `
                <tr>
                    <td><strong>${k.label}</strong></td>
                    <td class="font-mono muted-text" style="font-size: 0.76rem;">${hashPreview}</td>
                    <td class="muted-text">${dateStr}</td>
                    <td>
                        <button class="btn btn-danger btn-icon-only" onclick="revokeAPIKey(${k.id})" title="Revoke Key Access">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
        
        lucide.createIcons();
    } catch (e) {
        showToast("Error retrieving API access keys: " + e.message, "danger");
    }
}

async function generateAPIKey(event) {
    event.preventDefault();
    const labelInput = document.getElementById("key-label");
    const label = labelInput.value;

    try {
        const response = await fetch(`${API_BASE}/keys`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label })
        });
        
        if (!response.ok) throw new Error("Failed to generate token");
        
        const data = await response.json();
        
        labelInput.value = "";
        
        // Populate and reveal key box
        const revealContainer = document.getElementById("key-reveal-container");
        const revealInput = document.getElementById("revealed-raw-key");
        
        revealInput.value = data.raw_api_key;
        revealContainer.classList.remove("hide");
        
        showToast("Secure Access Key generated successfully!", "success");
        
        // Highlight explorer sandbox with new key automatically
        document.getElementById("explorer-api-key").value = data.raw_api_key;
        updateExplorerTip();
        
        refreshAll();
    } catch (e) {
        showToast("Error generating token: " + e.message, "danger");
    }
}

function copyRevealedKey() {
    const keyInput = document.getElementById("revealed-raw-key");
    keyInput.select();
    keyInput.setSelectionRange(0, 99999); // Mobile
    navigator.clipboard.writeText(keyInput.value);
    
    // Toggle copy success vector icon
    const icon = document.getElementById("copy-key-icon");
    icon.classList.remove("lucide-copy");
    icon.classList.add("lucide-check");
    setTimeout(() => {
        icon.classList.remove("lucide-check");
        icon.classList.add("lucide-copy");
    }, 1500);

    showToast("API Key copied to clipboard.", "success");
}

async function revokeAPIKey(id) {
    showConfirm(
        "Revoke API Key?",
        "Any external app using this token will immediately lose access. This cannot be undone.",
        "Revoke Key",
        async () => {
            try {
                const response = await fetch(`${API_BASE}/keys/${id}`, {
                    method: "DELETE"
                });

                if (!response.ok) throw new Error("Revocation failed");

                showToast("API Key successfully revoked.", "success");
                refreshAll();
            } catch (e) {
                showToast("Error revoking key: " + e.message, "danger");
            }
        }
    );
}


// =====================================================================
// UNIFIED API GATEWAY EXPLORER (SANDBOX CONSOLE)
// =====================================================================
function updateExplorerTip() {
    const key = document.getElementById("explorer-api-key").value || "<API_KEY>";
    const category = document.getElementById("explorer-endpoint").value;
    
    const curlCode = `curl -H "X-API-Key: ${key}" ${window.location.origin}${API_BASE}/${category}`;
    document.getElementById("curl-preview-box").innerText = curlCode;
}

async function runExplorerQuery() {
    const key = document.getElementById("explorer-api-key").value;
    const category = document.getElementById("explorer-endpoint").value;
    const consoleBox = document.getElementById("explorer-console-output");
    
    const statusBadge = document.getElementById("explorer-status-badge");
    const timeBadge = document.getElementById("explorer-time-badge");
    
    statusBadge.classList.add("hide");
    timeBadge.classList.add("hide");
    consoleBox.innerText = "Contacting unified gateway endpoint /api/v1/" + category + "...";

    const startTime = performance.now();

    try {
        const response = await fetch(`${API_BASE}/${category}`, {
            headers: {
                "X-API-Key": key
            }
        });
        
        const endTime = performance.now();
        const duration = Math.round(endTime - startTime);

        const data = await response.json();
        
        statusBadge.innerText = `${response.status} ${response.statusText || (response.status === 200 ? 'OK' : 'Unauthorized')}`;
        statusBadge.className = response.status === 200 ? "badge badge-success animate-fade-in" : "badge badge-danger animate-fade-in";
        statusBadge.classList.remove("hide");

        timeBadge.innerText = `${duration}ms`;
        timeBadge.className = "badge badge-info animate-fade-in";
        timeBadge.classList.remove("hide");

        consoleBox.innerText = JSON.stringify(data, null, 2);
        
        if (response.status === 200) {
            showToast("Aggregator fetch completed successfully.", "success");
        } else {
            showToast("Fetch unauthorized: " + (data.detail || "Authentication key failure"), "danger");
        }
    } catch (e) {
        consoleBox.innerText = "GATEWAY ERROR: " + e.message;
        showToast("Error contacting gateway: " + e.message, "danger");
    }
}

function copyCurlCommand() {
    const text = document.getElementById("curl-preview-box").innerText;
    navigator.clipboard.writeText(text);
    showToast("cURL command copied to clipboard.", "success");
}

// =====================================================================
// CUSTOM CONFIRM DIALOG
// =====================================================================
let _confirmCallback = null;

function showConfirm(title, message, okLabel, callback) {
    document.getElementById("confirm-title").innerText = title;
    document.getElementById("confirm-message").innerText = message;
    document.getElementById("confirm-ok-btn").innerText = okLabel || "Confirm";
    _confirmCallback = callback;
    document.getElementById("confirm-dialog").classList.remove("hide");
    lucide.createIcons();
}

function cancelConfirm() {
    _confirmCallback = null;
    document.getElementById("confirm-dialog").classList.add("hide");
}

function confirmOk() {
    document.getElementById("confirm-dialog").classList.add("hide");
    if (_confirmCallback) {
        _confirmCallback();
        _confirmCallback = null;
    }
}

// =====================================================================
// DYNAMIC UTILITY COMPONENT SYSTEMS
// =====================================================================
function showToast(msg, type = "primary") {
    const toast = document.getElementById("toast-notif");
    const icon = document.getElementById("toast-icon");
    const message = document.getElementById("toast-message");
    
    // Set icons
    const icons = {
        "success": "check-circle",
        "danger": "x-circle",
        "warning": "alert-triangle",
        "primary": "info"
    };
    
    icon.setAttribute("data-lucide", icons[type] || "info");
    message.innerText = msg;
    
    // Set border glows
    const glows = {
        "success": "var(--teal)",
        "danger": "var(--coral)",
        "warning": "var(--orange)",
        "primary": "var(--primary)"
    };
    toast.style.borderColor = glows[type] || "var(--primary)";
    
    toast.classList.remove("hide");
    lucide.createIcons();

    setTimeout(() => {
        toast.classList.add("hide");
    }, 4000);
}
