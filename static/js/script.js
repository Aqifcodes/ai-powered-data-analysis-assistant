// Global variables to hold active dataset preview state
let currentHeaders = [];
let currentRows = [];
let filteredRows = [];
let currentSortColumn = null;
let currentSortDirection = 'asc';

// Wait for the DOM to be fully loaded
document.addEventListener("DOMContentLoaded", () => {
    initUploadEvents();
    initSampleDataEvents();
    initSearchAndSortEvents();
    initResetEvents();
});

/* ==========================================================================
   UPLOAD EVENTS AND DRAG & DROP
   ========================================================================== */
function initUploadEvents() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    
    // Trigger file selection dialog when clicking on the drop zone
    dropZone.addEventListener("click", () => fileInput.click());
    
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Drag-and-drop event handlers
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });
}

/* ==========================================================================
   SAMPLE DATA LOADING
   ========================================================================== */
function initSampleDataEvents() {
    const btnSales = document.getElementById("btn-sample-sales");
    const btnHR = document.getElementById("btn-sample-hr");

    btnSales.addEventListener("click", () => loadSampleDataset("sample_sales.csv"));
    btnHR.addEventListener("click", () => loadSampleDataset("sample_hr.csv"));
}

async function loadSampleDataset(fileName) {
    try {
        showLoadingState();
        updateProgress('step-upload', 'active');
        
        // Fetch the static sample file from the server
        const response = await fetch(`/static/${fileName}`);
        if (!response.ok) {
            throw new Error(`Failed to load sample dataset: ${response.statusText}`);
        }
        
        const blob = await response.blob();
        // Construct a File object from the blob to upload it through the standard endpoint
        const file = new File([blob], fileName.replace('sample_', ''), { type: 'text/csv' });
        
        // Simulate minor upload delay for premium UX
        setTimeout(() => {
            updateProgress('step-upload', 'success');
            sendToServer(file);
        }, 600);
        
    } catch (error) {
        alert("Error loading sample dataset: " + error.message);
        resetDashboardState();
    }
}

/* ==========================================================================
   FILE UPLOAD PROCESSING
   ========================================================================== */
function handleFileUpload(file) {
    // Basic verification of format
    if (!file.name.toLowerCase().endsWith('.csv')) {
        alert("Please upload a valid CSV file (.csv).");
        return;
    }
    
    showLoadingState();
    updateProgress('step-upload', 'active');
    
    // Simulate upload delay for progress bar aesthetics
    setTimeout(() => {
        updateProgress('step-upload', 'success');
        sendToServer(file);
    }, 600);
}

function sendToServer(file) {
    const formData = new FormData();
    formData.append('file', file);

    updateProgress('step-inspect', 'active');

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            // Attempt to parse structured validation error
            return response.json().then(err => { throw new Error(err.error || "Server processing failed."); });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Animate pipeline workflow steps before revealing the completed dashboard
            animatePipelineProgress(data);
        } else {
            throw new Error(data.error || "Failed to process dataset.");
        }
    })
    .catch(error => {
        alert("Error: " + error.message);
        resetDashboardState();
    });
}

/* ==========================================================================
   PROGRESS ANIMATION TIMELINES
   ========================================================================== */
function showLoadingState() {
    document.getElementById("upload-section").classList.add("hidden");
    document.getElementById("progress-section").classList.remove("hidden");
    
    // Reset all step classes to pending
    const steps = document.querySelectorAll(".step");
    steps.forEach(step => {
        step.className = "step pending";
        step.querySelector("i").className = "fa-solid fa-circle-dot";
    });
}

function updateProgress(stepId, state) {
    const stepElement = document.getElementById(stepId);
    if (!stepElement) return;

    if (state === 'active') {
        stepElement.className = "step active";
        stepElement.querySelector("i").className = "fa-solid fa-spinner fa-spin";
    } else if (state === 'success') {
        stepElement.className = "step success";
        stepElement.querySelector("i").className = "fa-solid fa-circle-check";
    }
}

function animatePipelineProgress(data) {
    // List of keys to step through in sequence
    const pipelineSequence = [
        { current: 'step-inspect', next: 'step-missing', delay: 400 },
        { current: 'step-missing', next: 'step-outliers', delay: 500 },
        { current: 'step-outliers', next: 'step-duplicates', delay: 450 },
        { current: 'step-duplicates', next: 'step-kpis', delay: 400 },
        { current: 'step-kpis', next: 'step-insights', delay: 500 },
        { current: 'step-insights', next: 'step-ready', delay: 600 }
    ];

    let currentIdx = 0;

    function nextStep() {
        if (currentIdx < pipelineSequence.length) {
            const step = pipelineSequence[currentIdx];
            updateProgress(step.current, 'success');
            updateProgress(step.next, 'active');
            currentIdx++;
            setTimeout(nextStep, step.delay);
        } else {
            // Last step: mark ready and render dashboard
            updateProgress('step-ready', 'success');
            setTimeout(() => {
                renderDashboard(data);
            }, 500);
        }
    }

    setTimeout(nextStep, 500);
}

/* ==========================================================================
   RENDER DASHBOARD CONTROLS
   ========================================================================== */
function renderDashboard(data) {
    // 1. Hide progress screen and display dashboard
    document.getElementById("progress-section").classList.add("hidden");
    const dashContainer = document.getElementById("dashboard-container");
    dashContainer.classList.remove("hidden");

    // 2. Render metadata info cards
    const info = data.dataset_info;
    document.getElementById("meta-filename").innerText = info.filename;
    document.getElementById("meta-rows").innerText = info.rows.toLocaleString();
    document.getElementById("meta-cols").innerText = info.cols.toLocaleString();
    document.getElementById("meta-size").innerText = info.size;
    document.getElementById("meta-missing").innerText = info.missing_pct;

    // 3. Setup download button link
    const downloadBtn = document.getElementById("btn-download-cleaned");
    downloadBtn.setAttribute("href", data.download_url);

    // 4. Render Preprocessing logs
    renderLogs(data.summary_logs);

    // 5. Render KPIs
    renderKPIs(data.kpis);

    // 6. Render Key Insights
    renderInsights(data.insights);

    // 7. Store dataset preview locally in memory for interactive table searching and sorting
    currentHeaders = data.preview_headers;
    currentRows = data.preview_rows;
    filteredRows = [...currentRows];
    
    // Reset sorting columns indicators
    currentSortColumn = null;
    currentSortDirection = 'asc';
    document.getElementById("table-search").value = "";
    
    renderTable();
}

function renderLogs(logs) {
    const container = document.getElementById("summary-logs-container");
    container.innerHTML = ""; // Clear contents
    
    if (!logs || logs.length === 0) {
        container.innerHTML = `<div class="log-item fallback"><i class="fa-solid fa-circle-info"></i> No preprocessing actions were required. The dataset is already clean!</div>`;
        return;
    }

    logs.forEach(log => {
        const logDiv = document.createElement("div");
        logDiv.className = "log-item animate-fade-in";
        
        let iconClass = "fa-solid fa-info-circle";
        
        // Categorize logs dynamically to color code logs beautifully
        if (log.toLowerCase().includes("duplicate")) {
            logDiv.classList.add("duplicate");
            iconClass = "fa-solid fa-clone";
        } else if (log.toLowerCase().includes("median")) {
            logDiv.classList.add("missing-median");
            iconClass = "fa-solid fa-chart-bar-mean"; // Median represents central value
            iconClass = "fa-solid fa-arrows-split-up-and-left";
        } else if (log.toLowerCase().includes("mean")) {
            logDiv.classList.add("missing-mean");
            iconClass = "fa-solid fa-calculator";
        } else if (log.toLowerCase().includes("datetime")) {
            logDiv.classList.add("date-convert");
            iconClass = "fa-solid fa-calendar-days";
        } else if (log.toLowerCase().includes("mode")) {
            logDiv.classList.add("missing-mean");
            iconClass = "fa-solid fa-check-double";
        }
        
        logDiv.innerHTML = `<i class="${iconClass}"></i> ${log}`;
        container.appendChild(logDiv);
    });
}

function renderKPIs(kpis) {
    const container = document.getElementById("kpi-container");
    container.innerHTML = "";
    
    kpis.forEach(kpi => {
        const card = document.createElement("div");
        card.className = `kpi-card ${kpi.color} animate-fade-in`;
        
        card.innerHTML = `
            <div class="kpi-info">
                <span class="kpi-card-label">${kpi.label}</span>
                <span class="kpi-card-value">${kpi.value}</span>
            </div>
            <div class="kpi-icon-wrapper">
                <i class="fa-solid ${kpi.icon}"></i>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderInsights(insights) {
    const list = document.getElementById("insights-list");
    const badge = document.getElementById("insights-count-badge");
    list.innerHTML = "";

    if (!insights || insights.length === 0) {
        list.innerHTML = `<li class="insight-item fallback"><i class="fa-solid fa-circle-info"></i> No specific insights could be generated for this dataset.</li>`;
        if (badge) badge.innerText = "";
        return;
    }

    // Update the badge count
    if (badge) badge.innerText = `${insights.length} insight${insights.length > 1 ? 's' : ''}`;

    insights.forEach((text, index) => {
        const li = document.createElement("li");
        li.className = "insight-item animate-fade-in";
        // Stagger each bullet slightly so they cascade in
        li.style.animationDelay = `${index * 0.07}s`;
        li.innerHTML = `<i class="fa-solid fa-circle-dot insight-dot"></i><span>${text}</span>`;
        list.appendChild(li);
    });
}

/* ==========================================================================
   DATA TABLE: SEARCH & SORT
   ========================================================================== */
function initSearchAndSortEvents() {
    const searchInput = document.getElementById("table-search");
    
    // Fuzzy text searching
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        
        if (query === "") {
            filteredRows = [...currentRows];
        } else {
            // Search all cells of each row for matches
            filteredRows = currentRows.filter(row => {
                return Object.values(row).some(val => {
                    return String(val).toLowerCase().includes(query);
                });
            });
        }
        renderTableRows();
    });
}

function renderTable() {
    renderTableHeaders();
    renderTableRows();
}

function renderTableHeaders() {
    const headerRow = document.getElementById("table-headers");
    headerRow.innerHTML = "";
    
    currentHeaders.forEach(header => {
        const th = document.createElement("th");
        th.innerHTML = `${header.replace('_', ' ')} <i class="fa-solid fa-sort"></i>`;
        
        // Add sorting click handlers
        th.addEventListener("click", () => {
            sortTable(header);
        });
        
        headerRow.appendChild(th);
    });
}

function renderTableRows() {
    const tbody = document.getElementById("table-rows");
    tbody.innerHTML = "";
    
    if (filteredRows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${currentHeaders.length}" style="text-align: center; padding: 2rem;">No matching preview records found.</td></tr>`;
        return;
    }

    filteredRows.forEach(row => {
        const tr = document.createElement("tr");
        currentHeaders.forEach(header => {
            const td = document.createElement("td");
            // Fill cells, replacing undefined/null with empty strings
            td.innerText = row[header] !== undefined ? row[header] : "";
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function sortTable(columnName) {
    if (currentSortColumn === columnName) {
        // Toggle direction if clicking same column
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        // Default to asc for new columns
        currentSortColumn = columnName;
        currentSortDirection = 'asc';
    }

    // Sort rows list
    filteredRows.sort((a, b) => {
        let valA = a[columnName];
        let valB = b[columnName];
        
        // Handle numeric conversion comparison
        const numA = Number(valA);
        const numB = Number(valB);
        
        if (!isNaN(numA) && !isNaN(numB)) {
            valA = numA;
            valB = numB;
        } else {
            // Standard string clean compare
            valA = String(valA).toLowerCase();
            valB = String(valB).toLowerCase();
        }

        if (valA < valB) return currentSortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return currentSortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    // Update sort icons in UI
    const thElements = document.querySelectorAll("#table-headers th");
    currentHeaders.forEach((header, idx) => {
        const icon = thElements[idx].querySelector("i");
        if (header === columnName) {
            icon.className = currentSortDirection === 'asc' ? "fa-solid fa-sort-up text-primary" : "fa-solid fa-sort-down text-primary";
        } else {
            icon.className = "fa-solid fa-sort";
        }
    });

    renderTableRows();
}

/* ==========================================================================
   RESET / STATE CLEANUP
   ========================================================================== */
function initResetEvents() {
    const btnReset = document.getElementById("btn-upload-another");
    btnReset.addEventListener("click", resetDashboardState);
}

function resetDashboardState() {
    // Hide dashboard sections, reveal initial upload card
    document.getElementById("dashboard-container").classList.add("hidden");
    document.getElementById("progress-section").classList.add("hidden");
    document.getElementById("upload-section").classList.remove("hidden");
    
    // Clear the file input values
    document.getElementById("file-input").value = "";
    
    // Reset state variables
    currentHeaders = [];
    currentRows = [];
    filteredRows = [];
    currentSortColumn = null;
    currentSortDirection = 'asc';
}
