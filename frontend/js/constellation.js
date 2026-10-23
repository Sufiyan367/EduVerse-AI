/**
 * EduVerse AI — Knowledge Constellation Module
 * Renders an interactive SVG concept graph and an accessible linear list alternative.
 */

export class KnowledgeConstellation {
  constructor(containerId, listContainerId, onConceptSelect) {
    this.container = document.getElementById(containerId);
    this.listContainer = document.getElementById(listContainerId);
    this.onConceptSelect = onConceptSelect;

    this.nodes = [];
    this.edges = [];
    this.selectedNodeId = null;
    this.viewMode = "graph"; // "graph" or "list"

    this.svgNS = "http://www.w3.org/2000/svg";
    this.initDOM();
  }

  initDOM() {
    if (!this.container) return;

    this.container.innerHTML = `
      <svg class="constellation-svg" id="constellation-svg" viewBox="0 0 800 450" preserveAspectRatio="xMidYMid meet">
        <defs>
          <!-- Arrow marker for directed edges -->
          <marker id="edge-arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(114, 217, 204, 0.6)" />
          </marker>
          <marker id="edge-arrow-active" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#72D9CC" />
          </marker>
          <!-- Subtle glow filter -->
          <filter id="node-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#72D9CC" flood-opacity="0.6"/>
          </filter>
        </defs>
        <g id="edges-group"></g>
        <g id="nodes-group"></g>
      </svg>
      <div class="node-inspector-drawer" id="node-inspector">
        <div class="inspector-info">
          <div class="inspector-header">
            <span class="inspector-title" id="inspector-title">Select a concept</span>
            <span class="badge badge-teal" id="inspector-category">Core</span>
            <span class="badge badge-neutral" id="inspector-page">Page 1</span>
          </div>
          <div class="inspector-desc" id="inspector-definition">Click any node to explore its syllabus definition.</div>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-sm btn-secondary" id="btn-inspector-simplify">
            <span>✨</span> Simplify
          </button>
          <button class="btn btn-sm btn-primary" id="btn-inspector-ask">
            <span>💬</span> Ask Tutor
          </button>
        </div>
      </div>
    `;

    // Hook up inspector action buttons
    const btnAsk = document.getElementById("btn-inspector-ask");
    const btnSimplify = document.getElementById("btn-inspector-simplify");

    if (btnAsk) {
      btnAsk.addEventListener("click", () => {
        const node = this.getSelectedNode();
        if (node && this.onConceptSelect) {
          this.onConceptSelect(node, "ask");
        }
      });
    }

    if (btnSimplify) {
      btnSimplify.addEventListener("click", () => {
        const node = this.getSelectedNode();
        if (node && this.onConceptSelect) {
          this.onConceptSelect(node, "simplify");
        }
      });
    }
  }

  /**
   * Sets the constellation graph data and renders both SVG and accessible list view.
   */
  setData(nodes = [], edges = []) {
    this.nodes = nodes;
    this.edges = edges;
    this.selectedNodeId = null;

    this.calculatePositions();
    this.renderGraph();
    this.renderList();
    this.hideInspector();
  }

  /**
   * Computes clean, deterministic radial positions around the viewport center.
   */
  calculatePositions() {
    const width = 800;
    const height = 450;
    const cx = width / 2;
    const cy = height / 2;
    const count = this.nodes.length;

    if (count === 0) return;

    if (count === 1) {
      this.nodes[0].x = cx;
      this.nodes[0].y = cy;
      return;
    }

    // Place central core node at center, rest in concentric ellipse
    const radiusX = Math.min(cx - 80, 260);
    const radiusY = Math.min(cy - 60, 150);

    this.nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      node.x = Math.round(cx + radiusX * Math.cos(angle));
      node.y = Math.round(cy + radiusY * Math.sin(angle));
    });
  }

  /**
   * Renders SVG nodes and directed edges.
   */
  renderGraph() {
    const edgesGroup = document.getElementById("edges-group");
    const nodesGroup = document.getElementById("nodes-group");
    if (!edgesGroup || !nodesGroup) return;

    edgesGroup.innerHTML = "";
    nodesGroup.innerHTML = "";

    const nodeMap = new Map(this.nodes.map((n) => [n.id, n]));

    // Render Edges
    this.edges.forEach((edge, idx) => {
      const src = nodeMap.get(edge.source);
      const tgt = nodeMap.get(edge.target);
      if (!src || !tgt) return;

      const edgePath = document.createElementNS(this.svgNS, "path");
      edgePath.setAttribute("class", "constellation-edge");
      edgePath.setAttribute("id", `edge-${edge.source}-${edge.target}`);
      edgePath.setAttribute("marker-end", "url(#edge-arrow)");

      // Quadratic curve for aesthetic flow
      const midX = (src.x + tgt.x) / 2;
      const midY = (src.y + tgt.y) / 2;
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const curveOffset = ((idx % 2 === 0 ? 1 : -1) * Math.min(30, Math.sqrt(dx * dx + dy * dy) * 0.1));
      const cx = midX - dy * (curveOffset / 100);
      const cy = midY + dx * (curveOffset / 100);

      const d = `M ${src.x} ${src.y} Q ${cx} ${cy} ${tgt.x} ${tgt.y}`;
      edgePath.setAttribute("d", d);
      edgesGroup.appendChild(edgePath);

      // Edge relationship text label
      if (edge.relationship) {
        const labelText = document.createElementNS(this.svgNS, "text");
        labelText.setAttribute("class", "edge-label-text");
        labelText.setAttribute("x", cx);
        labelText.setAttribute("y", cy - 4);
        labelText.setAttribute("text-anchor", "middle");
        labelText.textContent = edge.relationship;
        edgesGroup.appendChild(labelText);
      }
    });

    // Render Nodes
    this.nodes.forEach((node) => {
      const g = document.createElementNS(this.svgNS, "g");
      g.setAttribute("class", "constellation-node");
      g.setAttribute("id", `node-${node.id}`);
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute("aria-label", `Concept: ${node.label}, Category: ${node.category}`);

      const circle = document.createElementNS(this.svgNS, "circle");
      circle.setAttribute("class", "node-bg");
      circle.setAttribute("cx", node.x);
      circle.setAttribute("cy", node.y);
      circle.setAttribute("r", 26);

      const text = document.createElementNS(this.svgNS, "text");
      text.setAttribute("class", "node-label");
      text.setAttribute("x", node.x);
      text.setAttribute("y", node.y + 36);
      text.textContent = node.label.length > 20 ? node.label.substring(0, 18) + "…" : node.label;

      g.appendChild(circle);
      g.appendChild(text);

      // Keyboard & Click Interaction
      const handleSelect = (e) => {
        e.stopPropagation();
        this.selectNode(node.id);
      };

      g.addEventListener("click", handleSelect);
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleSelect(e);
        }
      });

      nodesGroup.appendChild(g);
    });
  }

  /**
   * Renders the accessible semantic HTML list alternative.
   */
  renderList() {
    if (!this.listContainer) return;
    this.listContainer.innerHTML = "";

    if (this.nodes.length === 0) {
      this.listContainer.innerHTML = `
        <div class="empty-state">
          <p class="empty-state-title">No concepts available</p>
          <p class="empty-state-desc">Upload a PDF or load the ML syllabus to generate the constellation.</p>
        </div>
      `;
      return;
    }

    const heading = document.createElement("h3");
    heading.className = "input-label";
    heading.textContent = `Extracted Syllabus Concepts (${this.nodes.length})`;
    this.listContainer.appendChild(heading);

    const listGroup = document.createElement("div");
    listGroup.className = "doc-list";

    this.nodes.forEach((node) => {
      const item = document.createElement("div");
      item.className = "doc-item";
      item.setAttribute("tabindex", "0");
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", `${node.label}, ${node.category}`);

      item.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:2px; flex:1;">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="doc-item-title">${node.label}</span>
            <span class="badge badge-teal">${node.category}</span>
          </div>
          <p style="font-size:0.78rem; color:var(--text-secondary); margin-top:2px;">${node.definition}</p>
        </div>
        <span class="badge badge-neutral" style="margin-left:0.5rem;">Page ${node.page_reference}</span>
      `;

      item.addEventListener("click", () => {
        this.selectNode(node.id);
      });
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.selectNode(node.id);
        }
      });

      listGroup.appendChild(item);
    });

    this.listContainer.appendChild(listGroup);
  }

  /**
   * Highlights the selected node, dims unrelated edges, and reveals the inspector card.
   */
  selectNode(nodeId) {
    this.selectedNodeId = nodeId;
    const node = this.nodes.find((n) => n.id === nodeId);
    if (!node) return;

    // 1. Update node classes
    this.nodes.forEach((n) => {
      const el = document.getElementById(`node-${n.id}`);
      if (el) {
        if (n.id === nodeId) {
          el.classList.add("active");
        } else {
          el.classList.remove("active");
        }
      }
    });

    // 2. Highlight connected edges
    this.edges.forEach((edge) => {
      const edgeEl = document.getElementById(`edge-${edge.source}-${edge.target}`);
      if (edgeEl) {
        if (edge.source === nodeId || edge.target === nodeId) {
          edgeEl.classList.add("highlighted");
          edgeEl.setAttribute("marker-end", "url(#edge-arrow-active)");
        } else {
          edgeEl.classList.remove("highlighted");
          edgeEl.setAttribute("marker-end", "url(#edge-arrow)");
        }
      }
    });

    // 3. Update and open slide-up inspector
    this.showInspector(node);
  }

  showInspector(node) {
    const drawer = document.getElementById("node-inspector");
    const title = document.getElementById("inspector-title");
    const cat = document.getElementById("inspector-category");
    const page = document.getElementById("inspector-page");
    const def = document.getElementById("inspector-definition");

    if (drawer && title && cat && page && def) {
      title.textContent = node.label;
      cat.textContent = node.category || "Core Concept";
      page.textContent = `Page ${node.page_reference || 1}`;
      def.textContent = node.definition || "No definition available.";
      drawer.classList.add("open");
    }
  }

  hideInspector() {
    const drawer = document.getElementById("node-inspector");
    if (drawer) {
      drawer.classList.remove("open");
    }
  }

  getSelectedNode() {
    return this.nodes.find((n) => n.id === this.selectedNodeId);
  }

  toggleView(mode) {
    this.viewMode = mode;
    const svg = document.getElementById("constellation-svg");
    if (this.viewMode === "list") {
      if (svg) svg.style.display = "none";
      if (this.listContainer) this.listContainer.classList.add("active");
      this.hideInspector();
    } else {
      if (svg) svg.style.display = "block";
      if (this.listContainer) this.listContainer.classList.remove("active");
    }
  }
}
