/**
 * EduVerse AI — Workspace Orchestrator
 * Integrates Document Library, Knowledge Constellation, Tutor, and Practice modules.
 */

import { api } from "./api.js";
import { KnowledgeConstellation } from "./constellation.js";
import { TutorManager } from "./tutor.js";
import { PracticeManager } from "./practice.js";

class EduVerseWorkspace {
  constructor() {
    this.activeDocId = null;
    this.activeDoc = null;
    this.documents = [];

    this.constellation = null;
    this.tutor = null;
    this.practice = null;
  }

  async init() {
    this.initModules();
    this.initGlobalEvents();
    await this.checkHealth();
    await this.loadInitialDocuments();
  }

  initModules() {
    // 1. Initialize Knowledge Constellation
    this.constellation = new KnowledgeConstellation(
      "constellation-canvas-container",
      "constellation-list-view",
      (node, action) => this.handleConceptAction(node, action)
    );

    // 2. Initialize Tutor Manager
    this.tutor = new TutorManager(
      "tutor-messages",
      "tutor-input",
      "btn-send-tutor",
      (query) => this.handleTutorQuery(query)
    );

    // 3. Initialize Practice & Assessment Manager
    this.practice = new PracticeManager(
      "quiz-view-container",
      "history-view-container",
      {
        onGenerate: () => this.handleGenerateQuiz(),
        onSubmit: (quizId, answers) => this.handleSubmitQuiz(quizId, answers),
        onFetchHistory: () => this.refreshHistory(),
      }
    );
  }

  initGlobalEvents() {
    // View Toggle for Constellation (Graph vs List)
    const btnGraph = document.getElementById("btn-view-graph");
    const btnList = document.getElementById("btn-view-list");

    if (btnGraph && btnList) {
      btnGraph.addEventListener("click", () => {
        btnGraph.classList.add("active");
        btnList.classList.remove("active");
        this.constellation.toggleView("graph");
      });

      btnList.addEventListener("click", () => {
        btnList.classList.add("active");
        btnGraph.classList.remove("active");
        this.constellation.toggleView("list");
      });
    }

    // Practice Tabs (Active Quiz vs Persisted History)
    const tabActiveQuiz = document.getElementById("tab-active-quiz");
    const tabHistory = document.getElementById("tab-history");
    const viewActiveQuiz = document.getElementById("quiz-view-container");
    const viewHistory = document.getElementById("history-view-container");

    if (tabActiveQuiz && tabHistory) {
      tabActiveQuiz.addEventListener("click", () => {
        tabActiveQuiz.classList.add("active");
        tabHistory.classList.remove("active");
        viewActiveQuiz.style.display = "flex";
        viewHistory.style.display = "none";
      });

      tabHistory.addEventListener("click", () => {
        tabHistory.classList.add("active");
        tabActiveQuiz.classList.remove("active");
        viewActiveQuiz.style.display = "none";
        viewHistory.style.display = "flex";
        this.refreshHistory();
      });
    }

    // PDF Upload Dropzone Events
    const dropzone = document.getElementById("pdf-dropzone");
    const fileInput = document.getElementById("pdf-file-input");

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", () => fileInput.click());

      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("drag-active");
      });

      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("drag-active");
      });

      dropzone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag-active");
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          await this.handleFileUpload(e.dataTransfer.files[0]);
        }
      });

      fileInput.addEventListener("change", async (e) => {
        if (e.target.files && e.target.files.length > 0) {
          await this.handleFileUpload(e.target.files[0]);
        }
      });
    }

    // Load Sample Notes Button
    const btnSample = document.getElementById("btn-load-sample");
    if (btnSample) {
      btnSample.addEventListener("click", async () => {
        btnSample.disabled = true;
        btnSample.innerHTML = `<span>⏳</span> Loading Syllabus…`;
        try {
          const doc = await api.loadSampleNotes();
          await this.loadInitialDocuments();
          this.setActiveDocument(doc.doc_id);
        } catch (err) {
          alert(`Failed to load sample syllabus: ${err.message}`);
        } finally {
          btnSample.disabled = false;
          btnSample.innerHTML = `<span>⚡</span> Load ML Syllabus Sample`;
        }
      });
    }

    // Simplify Prompt Button beside input
    const btnSimplifyCurrent = document.getElementById("btn-simplify-current");
    if (btnSimplifyCurrent) {
      btnSimplifyCurrent.addEventListener("click", () => {
        const selectedNode = this.constellation.getSelectedNode();
        if (selectedNode) {
          this.handleConceptAction(selectedNode, "simplify");
        } else {
          const query = document.getElementById("tutor-input").value.trim();
          if (query) {
            this.handleSimplifyConcept(query);
          } else {
            alert("Select a concept node from the Constellation or enter a term to simplify.");
          }
        }
      });
    }

    // Reset Workspace Button
    const btnReset = document.getElementById("btn-reset-workspace");
    if (btnReset) {
      btnReset.addEventListener("click", () => {
        if (confirm("Reset workspace session and clear chat history?")) {
          document.getElementById("tutor-messages").innerHTML = "";
          this.tutor.appendTutorResponse({
            query: "Session Reset",
            answer: "Workspace reset. Select a document from your library or click on any Knowledge Constellation node to begin studying.",
            grounded: true,
            status: "supported",
          });
        }
      });
    }

    // Mobile Navigation Switcher
    const mobileBtns = document.querySelectorAll(".mobile-nav-btn");
    const workspaceGrid = document.querySelector(".workspace-grid");

    mobileBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        mobileBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        const targetTab = btn.getAttribute("data-tab");
        workspaceGrid.classList.remove("active-tab-library", "active-tab-practice");
        if (targetTab === "library") {
          workspaceGrid.classList.add("active-tab-library");
        } else if (targetTab === "practice") {
          workspaceGrid.classList.add("active-tab-practice");
        }
      });
    });
  }

  async checkHealth() {
    try {
      const health = await api.getHealth();
      const statusPill = document.getElementById("sqlite-status-pill");
      if (statusPill) {
        if (health.preview_mode) {
          statusPill.innerHTML = `
            <span class="status-dot" style="background:var(--accent-teal);"></span>
            <span>Static Preview Mode</span>
          `;
        } else {
          statusPill.innerHTML = `
            <span class="status-dot" style="background:var(--status-success);"></span>
            <span>SQLite Connected (${health.active_documents || 0} Docs)</span>
          `;
        }
      }
    } catch {
      const statusPill = document.getElementById("sqlite-status-pill");
      if (statusPill) {
        statusPill.innerHTML = `
          <span class="status-dot" style="background:var(--accent-teal);"></span>
          <span>Static Preview Mode</span>
        `;
      }
    }
  }

  async loadInitialDocuments() {
    try {
      this.documents = await api.listDocuments();
      this.renderDocumentList();

      if (this.documents.length > 0 && !this.activeDocId) {
        // Automatically activate the most recently uploaded document
        this.setActiveDocument(this.documents[0].doc_id);
      } else if (this.documents.length === 0) {
        // Auto-load sample ML document on initial first visit for instant delight
        const sampleDoc = await api.loadSampleNotes();
        this.documents = await api.listDocuments();
        this.renderDocumentList();
        this.setActiveDocument(sampleDoc.doc_id);
      }
    } catch (err) {
      console.warn("Document listing notice:", err);
    }
  }

  renderDocumentList() {
    const listEl = document.getElementById("doc-library-list");
    if (!listEl) return;

    if (this.documents.length === 0) {
      listEl.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); text-align:center; padding:1rem;">No documents uploaded.</div>`;
      return;
    }

    listEl.innerHTML = this.documents
      .map(
        (doc) => `
        <div class="doc-item ${doc.doc_id === this.activeDocId ? 'active' : ''}" data-docid="${doc.doc_id}">
          <div>
            <div class="doc-item-title" title="${doc.filename}">${doc.filename}</div>
            <div class="doc-item-meta">${doc.pages} Page(s) • ${doc.char_count.toLocaleString()} Chars</div>
          </div>
          <span class="badge ${doc.doc_id === this.activeDocId ? 'badge-teal' : 'badge-neutral'}">
            ${doc.doc_id === this.activeDocId ? 'Active' : 'Select'}
          </span>
        </div>
      `
      )
      .join("");

    listEl.querySelectorAll(".doc-item").forEach((item) => {
      item.addEventListener("click", () => {
        const docId = item.getAttribute("data-docid");
        this.setActiveDocument(docId);
      });
    });
  }

  async setActiveDocument(docId) {
    this.activeDocId = docId;
    this.activeDoc = this.documents.find((d) => d.doc_id === docId);

    // Update active badges in Header and Document List
    this.renderDocumentList();

    const activeBadge = document.getElementById("header-active-doc");
    if (activeBadge && this.activeDoc) {
      activeBadge.textContent = this.activeDoc.filename;
    }

    // Refresh Knowledge Constellation
    await this.refreshConstellation();

    // Reset Practice Quiz for newly selected document
    this.practice.setQuiz(null);
    this.refreshHistory();
  }

  async refreshConstellation() {
    if (!this.activeDocId) return;

    const countBadge = document.getElementById("constellation-count-badge");
    if (countBadge) countBadge.textContent = "Loading…";

    try {
      const data = await api.getConcepts(this.activeDocId);
      this.constellation.setData(data.nodes || [], data.edges || []);
      if (countBadge) {
        countBadge.textContent = `${(data.nodes || []).length} Concepts Grounded`;
      }
    } catch (err) {
      console.error("Constellation extraction failure:", err);
      if (countBadge) countBadge.textContent = "Graph Error";
    }
  }

  async handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Only PDF documents (.pdf) are supported.");
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      alert("File size exceeds 25 MB limit.");
      return;
    }

    const dropzone = document.getElementById("pdf-dropzone");
    const origHTML = dropzone.innerHTML;
    dropzone.innerHTML = `<div style="font-size:0.85rem; color:var(--accent-teal);">⏳ Extracting document with PyMuPDF…</div>`;

    try {
      const uploaded = await api.uploadPDF(file);
      this.documents = await api.listDocuments();
      this.setActiveDocument(uploaded.doc_id);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      dropzone.innerHTML = origHTML;
    }
  }

  async handleTutorQuery(query) {
    if (!this.activeDocId) {
      alert("Please select or upload a syllabus document first.");
      return;
    }

    this.tutor.appendUserMessage(query);
    this.tutor.clearInput();

    const loadingId = this.tutor.appendLoading("Querying syllabus notes…");

    try {
      const response = await api.queryTutor(this.activeDocId, query);
      this.tutor.removeLoading(loadingId);
      this.tutor.appendTutorResponse(response);
    } catch (err) {
      this.tutor.removeLoading(loadingId);
      this.tutor.appendTutorResponse({
        query,
        answer: `Encountered an error executing doubt resolution: ${err.message}`,
        grounded: false,
        status: "unsupported",
      });
    }
  }

  async handleSimplifyConcept(conceptName) {
    if (!this.activeDocId) return;

    const loadingId = this.tutor.appendLoading(`Decomposing "${conceptName}" into real-world mental model…`);

    try {
      const result = await api.simplifyConcept(this.activeDocId, conceptName);
      this.tutor.removeLoading(loadingId);
      this.tutor.appendSimplification(result);
    } catch (err) {
      this.tutor.removeLoading(loadingId);
      this.tutor.appendTutorResponse({
        query: `Simplify: ${conceptName}`,
        answer: `Failed to simplify concept: ${err.message}`,
        grounded: false,
        status: "unsupported",
      });
    }
  }

  handleConceptAction(node, action) {
    if (action === "ask") {
      this.tutor.setInputText(`Explain how ${node.label} works and its mathematical foundations according to our syllabus notes.`);
    } else if (action === "simplify") {
      this.handleSimplifyConcept(node.label);
    }
  }

  async handleGenerateQuiz() {
    if (!this.activeDocId) {
      alert("Please select or upload a study document first.");
      return;
    }

    const container = document.getElementById("quiz-view-container");
    container.innerHTML = `
      <div class="empty-state">
        <div class="status-dot status-dot-pulse" style="background:var(--accent-teal); width:14px; height:14px; margin-bottom:1rem;"></div>
        <p class="empty-state-title">Synthesizing Active Recall MCQs</p>
        <p class="empty-state-desc">Formulating questions directly grounded in the syllabus notes…</p>
      </div>
    `;

    try {
      const quiz = await api.generateQuiz(this.activeDocId, 3);
      this.practice.setQuiz(quiz);
    } catch (err) {
      alert(`Quiz synthesis error: ${err.message}`);
      this.practice.setQuiz(null);
    }
  }

  async handleSubmitQuiz(quizId, answers) {
    try {
      const result = await api.evaluateQuiz(quizId, answers);
      this.practice.showEvaluation(result);
      await this.refreshHistory();
    } catch (err) {
      alert(`Evaluation error: ${err.message}`);
    }
  }

  async refreshHistory() {
    try {
      const history = await api.getAssessmentHistory();
      this.practice.renderHistory(history);
    } catch (err) {
      console.warn("History fetch notice:", err);
    }
  }
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  const app = new EduVerseWorkspace();
  app.init();
});
