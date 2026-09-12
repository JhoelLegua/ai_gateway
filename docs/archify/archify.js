/**
 * AI Gateway Architectural Diagram Interactive Engine
 * Handles pan/zoom, interactive node inspection, dependency tracing and themes.
 */

class ArchifyViewer {
  constructor(options = {}) {
    this.container = document.querySelector(options.container || '.archify-canvas-container');
    this.svg = document.querySelector(options.svg || 'svg.archify-svg');
    this.viewport = document.querySelector(options.viewport || '#viewport');
    this.drawer = document.getElementById('archify-drawer');
    this.metadataStore = options.metadataStore || {};
    
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this.isPanning = false;
    this.startX = 0;
    this.startY = 0;
    this.selectedNodeId = null;

    this.checkIframeMode();
    this.initTheme();
    this.initPanZoom();
    this.initNodeInteractions();
    this.initControls();
  }

  checkIframeMode() {
    // If embedded in the main Hub iframe, hide redundant inner header to maximize canvas and eliminate nested navigation loops
    if (window.self !== window.top) {
      document.body.classList.add('in-iframe');
      const innerHeader = document.querySelector('.archify-header');
      if (innerHeader) {
        innerHeader.style.display = 'none';
      }
    }
  }

  initTheme() {
    const savedTheme = localStorage.getItem('archify_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.textContent = savedTheme === 'dark' ? 'Modo Claro' : 'Modo Oscuro';
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }
  }

  toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('archify_theme', next);
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.textContent = next === 'dark' ? 'Modo Claro' : 'Modo Oscuro';
    }
  }

  initPanZoom() {
    if (!this.container || !this.viewport) return;

    this.container.addEventListener('mousedown', (e) => {
      if (e.target.closest('.node-group') || e.target.closest('.archify-hud') || e.target.closest('.scenario-selector')) return;
      this.isPanning = true;
      this.startX = e.clientX - this.panX;
      this.startY = e.clientY - this.panY;
      this.container.classList.add('panning');
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isPanning) return;
      this.panX = e.clientX - this.startX;
      this.panY = e.clientY - this.startY;
      this.updateTransform();
    });

    window.addEventListener('mouseup', () => {
      this.isPanning = false;
      if (this.container) this.container.classList.remove('panning');
    });

    this.container.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = 1.12;
      const rect = this.container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const prevScale = this.scale;
      if (e.deltaY < 0) {
        this.scale = Math.min(this.scale * zoomFactor, 3.5);
      } else {
        this.scale = Math.max(this.scale / zoomFactor, 0.35);
      }

      this.panX = mouseX - (mouseX - this.panX) * (this.scale / prevScale);
      this.panY = mouseY - (mouseY - this.panY) * (this.scale / prevScale);
      this.updateTransform();
    }, { passive: false });
  }

  updateTransform() {
    if (!this.viewport) return;
    this.viewport.setAttribute('transform', `translate(${this.panX}, ${this.panY}) scale(${this.scale})`);
  }

  zoomIn() {
    this.scale = Math.min(this.scale * 1.25, 3.5);
    this.updateTransform();
  }

  zoomOut() {
    this.scale = Math.max(this.scale / 1.25, 0.35);
    this.updateTransform();
  }

  resetView() {
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this.updateTransform();
    this.clearSelection();
  }

  initControls() {
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnReset = document.getElementById('btn-reset');
    const btnCloseDrawer = document.getElementById('drawer-close');

    if (btnZoomIn) btnZoomIn.addEventListener('click', () => this.zoomIn());
    if (btnZoomOut) btnZoomOut.addEventListener('click', () => this.zoomOut());
    if (btnReset) btnReset.addEventListener('click', () => this.resetView());
    if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', () => this.closeDrawer());

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeDrawer();
        this.clearSelection();
      }
    });
  }

  initNodeInteractions() {
    const nodes = document.querySelectorAll('.node-group');
    nodes.forEach((node) => {
      node.addEventListener('click', (e) => {
        e.stopPropagation();
        const nodeId = node.getAttribute('id');
        this.selectNode(nodeId);
      });
    });

    if (this.svg) {
      this.svg.addEventListener('click', (e) => {
        if (!e.target.closest('.node-group')) {
          this.clearSelection();
          this.closeDrawer();
        }
      });
    }
  }

  selectNode(nodeId) {
    if (!nodeId) return;
    this.selectedNodeId = nodeId;

    const allNodes = document.querySelectorAll('.node-group');
    const allEdges = document.querySelectorAll('.edge-line');

    allNodes.forEach((n) => n.classList.remove('selected', 'dimmed'));
    allEdges.forEach((e) => e.classList.remove('active', 'dimmed'));

    const selectedElement = document.getElementById(nodeId);
    if (!selectedElement) return;

    selectedElement.classList.add('selected');

    const connectedNodeIds = new Set([nodeId]);
    allEdges.forEach((edge) => {
      const from = edge.getAttribute('data-from');
      const to = edge.getAttribute('data-to');

      if (from === nodeId || to === nodeId) {
        edge.classList.add('active');
        if (from) connectedNodeIds.add(from);
        if (to) connectedNodeIds.add(to);
      } else {
        edge.classList.add('dimmed');
      }
    });

    allNodes.forEach((n) => {
      if (!connectedNodeIds.has(n.getAttribute('id'))) {
        n.classList.add('dimmed');
      }
    });

    this.showNodeMetadata(nodeId);
  }

  clearSelection() {
    this.selectedNodeId = null;
    document.querySelectorAll('.node-group').forEach((n) => n.classList.remove('selected', 'dimmed'));
    document.querySelectorAll('.edge-line').forEach((e) => e.classList.remove('active', 'dimmed'));
  }

  showNodeMetadata(nodeId) {
    const meta = this.metadataStore[nodeId];
    if (!meta || !this.drawer) return;

    const titleEl = document.getElementById('drawer-node-title');
    const bodyEl = document.getElementById('drawer-node-body');

    if (titleEl) titleEl.textContent = meta.title || nodeId;
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="metadata-card">
          <div class="metadata-label">Módulo / Archivo</div>
          <div class="metadata-code">${meta.file || 'N/A'}</div>
        </div>
        <div class="metadata-card">
          <div class="metadata-label">Propósito Arquitectónico</div>
          <div class="metadata-value">${meta.description || 'Sin descripción'}</div>
        </div>
        ${meta.latency ? `
        <div class="metadata-card">
          <div class="metadata-label">Presupuesto de Latencia</div>
          <div class="metadata-value" style="color: var(--accent-cyan); font-weight: 600;">${meta.latency}</div>
        </div>` : ''}
        ${meta.mitre ? `
        <div class="metadata-card">
          <div class="metadata-label">Mitigación MITRE / OWASP</div>
          <div class="metadata-value" style="color: var(--accent-emerald);">${meta.mitre}</div>
        </div>` : ''}
        ${meta.io ? `
        <div class="metadata-card">
          <div class="metadata-label">Entrada / Salida</div>
          <div class="metadata-value">${meta.io}</div>
        </div>` : ''}
        ${meta.failureMode ? `
        <div class="metadata-card">
          <div class="metadata-label">Mecanismo de Falla / Resiliencia</div>
          <div class="metadata-value" style="color: var(--accent-amber);">${meta.failureMode}</div>
        </div>` : ''}
      `;
    }

    this.drawer.classList.add('open');
  }

  closeDrawer() {
    if (this.drawer) this.drawer.classList.remove('open');
  }
}

window.ArchifyViewer = ArchifyViewer;
