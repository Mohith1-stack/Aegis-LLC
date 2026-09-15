import './style.css';

let threatsMitigated = 0;
let isolationsCount = 0;
let isThreatActive = false;

// Initialize CPU Matrix
let CPU_CORES = 4;
const TIME_STEPS = 40;
let cpuData = Array(CPU_CORES).fill().map(() => Array(TIME_STEPS).fill(20));
let targetCpuLoads = Array(CPU_CORES).fill(20);

function initCPUMatrix() {
  const container = document.getElementById('cpu-matrix');
  container.innerHTML = '';
  
  for (let c = 0; c < CPU_CORES; c++) {
    const row = document.createElement('div');
    row.className = 'core-row';
    
    const label = document.createElement('span');
    label.className = 'core-label';
    label.textContent = `CORE ${c}`;
    
    const graph = document.createElement('div');
    graph.className = 'core-bars';
    graph.id = `graph-core-${c}`;
    
    for (let t = 0; t < TIME_STEPS; t++) {
      const bar = document.createElement('div');
      bar.className = 'bar';
      bar.style.height = `${cpuData[c][t]}%`;
      graph.appendChild(bar);
    }
    
    row.appendChild(label);
    row.appendChild(graph);
    container.appendChild(row);
  }
}

function updateCPUMatrix() {
  for (let c = 0; c < CPU_CORES; c++) {
    // Shift data left
    cpuData[c].shift();
    
    // Generate new data point based on actual target load + slight animation jitter
    let newLoad = targetCpuLoads[c] + (Math.random() * 10 - 5);
    newLoad = Math.max(2, Math.min(100, newLoad)); // Keep between 2% and 100%
    
    if (isThreatActive && c === 0) {
      newLoad = Math.max(newLoad, Math.random() * 20 + 80); // Threat load 80-100% on Core 0
    }
    
    cpuData[c].push(newLoad);
    
    // Update DOM
    const graph = document.getElementById(`graph-core-${c}`);
    if (graph) {
      const bars = graph.children;
      for (let t = 0; t < TIME_STEPS; t++) {
        bars[t].style.height = `${cpuData[c][t]}%`;
        if (cpuData[c][t] > 75 && isThreatActive && c === 0) {
          bars[t].classList.add('malicious');
        } else {
          bars[t].classList.remove('malicious');
        }
      }
    }
  }
}

function incrementKPIs() {
  const tracesEl = document.getElementById('traces-count');
  let currentTraces = parseInt(tracesEl.textContent.replace(/,/g, ''));
  currentTraces += Math.floor(Math.random() * 50);
  tracesEl.textContent = currentTraces.toLocaleString();
}

function logIncident(incident) {
  const tbody = document.getElementById('incidents-body');
  const row = document.createElement('tr');
  
  const time = new Date().toLocaleTimeString();
  
  row.innerHTML = `
    <td>${time}</td>
    <td style="font-family: monospace;">US-EAST-1-PROD</td>
    <td style="font-family: monospace;">${incident.pid}</td>
    <td style="color: var(--text-primary); font-weight: 500;">${incident.signature}</td>
    <td><span class="severity-pill critical">CRITICAL (99%)</span></td>
    <td><span class="action-pill">RESCTRL ISOLATION</span></td>
  `;
  
  tbody.insertBefore(row, tbody.firstChild);
  
  // Update KPIs
  threatsMitigated++;
  isolationsCount++;
  document.getElementById('threats-count').textContent = threatsMitigated;
  document.getElementById('isolations-count').textContent = isolationsCount;
  
  // Set global status
  isThreatActive = true;
  const globalStatus = document.getElementById('global-status');
  globalStatus.className = 'status-indicator threat';
  globalStatus.innerHTML = '<span class="status-dot"></span> THREAT CONTAINED';
  
  setTimeout(() => {
    isThreatActive = false;
    globalStatus.className = 'status-indicator';
    globalStatus.innerHTML = '<span class="status-dot"></span> System Secure';
  }, 4000);
}

document.getElementById('simulate-btn').addEventListener('click', () => {
  logIncident({
    pid: Math.floor(Math.random() * 10000) + 1000,
    signature: 'PRIME+PROBE CACHE LEAK'
  });
});

// Tab Routing Logic
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    if(!item.dataset.target) return;
    
    // Update active tab
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    
    // Update active view
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(item.dataset.target).classList.remove('hidden');
    
    if(item.dataset.target === 'view-specs') {
      fetchSpecs();
    }
  });
});

async function fetchSpecs() {
  const container = document.getElementById('specs-content');
  const banner = document.getElementById('vuln-banner');
  container.innerHTML = '<div class="loading-state" style="padding: 1.5rem; color: var(--text-muted);">Scanning hardware architecture...</div>';
  banner.classList.add('hidden');
  
  try {
    // We fetch from the Flask backend (make sure it's running on port 5000)
    const res = await fetch('http://localhost:5000/api/specs');
    const data = await res.json();
    
    if (data.error) throw new Error(data.error);
    
    container.innerHTML = `
      <div class="spec-item">
        <span class="spec-label">Operating System</span>
        <span class="spec-value">${data.os}</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">CPU Architecture</span>
        <span class="spec-value">${data.architecture}</span>
      </div>
      <div class="spec-item" style="grid-column: span 2;">
        <span class="spec-label">Processor</span>
        <span class="spec-value" style="font-family: monospace;">${data.processor}</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">Total RAM</span>
        <span class="spec-value">${data.ram_gb}</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">CPU Cores</span>
        <span class="spec-value">${data.physical_cores} Physical / ${data.logical_cores} Logical</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">Current CPU Freq</span>
        <span class="spec-value">${data.cpu_freq}</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">L3 Cache Size</span>
        <span class="spec-value">${data.l3_cache}</span>
      </div>
      <div class="spec-item" style="grid-column: span 2;">
        <span class="spec-label">Disk Storage</span>
        <span class="spec-value">${data.disk_total}</span>
      </div>
    `;
    
    if (data.vulnerable) {
      banner.classList.remove('hidden');
    }
    
  } catch (err) {
    container.innerHTML = `<div style="padding: 1.5rem; color: var(--status-critical);">Failed to fetch telemetry: ${err.message}</div>`;
  }
}

async function fetchDashboardStatus() {
  try {
    const res = await fetch('http://localhost:5000/api/status');
    const data = await res.json();
    if (data.active_processes) {
      document.getElementById('processes-count').innerHTML = `${data.active_processes} <span class="trend" style="color: var(--text-muted); font-size: 1rem; margin-left: 10px;">LIVE</span>`;
    }
    if (data.cpu_loads) {
      if (data.cpu_loads.length !== CPU_CORES && data.cpu_loads.length > 0) {
        CPU_CORES = data.cpu_loads.length;
        cpuData = Array(CPU_CORES).fill().map(() => Array(TIME_STEPS).fill(20));
        targetCpuLoads = Array(CPU_CORES).fill(20);
        initCPUMatrix();
      }
      for (let i = 0; i < CPU_CORES; i++) {
        targetCpuLoads[i] = data.cpu_loads[i];
      }
    }
  } catch (err) {}
}

document.getElementById('refresh-specs-btn').addEventListener('click', fetchSpecs);

// Init
initCPUMatrix();
fetchDashboardStatus();
setInterval(updateCPUMatrix, 250);
setInterval(incrementKPIs, 1000);
setInterval(fetchDashboardStatus, 3000);
