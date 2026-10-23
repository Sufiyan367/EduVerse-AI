/**
 * EduVerse AI — Evidence-First Tutor Module
 * Manages conversation stream, structured citations, unsupported alerts, and concept simplifications.
 */

export class TutorManager {
  constructor(messagesContainerId, inputId, sendBtnId, onSend) {
    this.container = document.getElementById(messagesContainerId);
    this.input = document.getElementById(inputId);
    this.sendBtn = document.getElementById(sendBtnId);
    this.onSend = onSend;

    this.initEvents();
  }

  initEvents() {
    if (this.sendBtn) {
      this.sendBtn.addEventListener("click", () => this.handleSend());
    }

    if (this.input) {
      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.handleSend();
        }
      });
    }
  }

  handleSend() {
    const text = this.input ? this.input.value.trim() : "";
    if (!text) return;
    if (this.onSend) {
      this.onSend(text);
    }
  }

  clearInput() {
    if (this.input) {
      this.input.value = "";
    }
  }

  setInputText(text) {
    if (this.input) {
      this.input.value = text;
      this.input.focus();
    }
  }

  /**
   * Appends student message bubble.
   */
  appendUserMessage(text) {
    if (!this.container) return;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble-user";
    bubble.innerHTML = `
      <div class="chat-sender-header">
        <span class="chat-sender-name" style="color:var(--accent-teal);">Student</span>
        <span style="font-size:0.7rem; color:var(--text-muted);">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div>${this.escapeHTML(text)}</div>
    `;

    this.container.appendChild(bubble);
    this.scrollToBottom();
  }

  /**
   * Appends grounded tutor response with structured evidence citations.
   */
  appendTutorResponse({ query, answer, status = "supported", grounded = true, evidence = [], context_excerpt = null }) {
    if (!this.container) return;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble-tutor";

    const isUnsupported = status === "unsupported" || !grounded;

    let statusBadgeHTML = isUnsupported
      ? `<span class="badge badge-danger">⚠️ Unsupported in Notes</span>`
      : `<span class="badge badge-teal">✓ Grounded in Syllabus</span>`;

    let evidenceHTML = "";
    if (isUnsupported) {
      evidenceHTML = `
        <div class="unsupported-banner" role="alert">
          <div>
            <strong>Out-of-Scope Notice:</strong> The question is not established by your active study notes. 
            To maintain strict academic integrity, EduVerse AI avoids hallucinating Derivations or facts absent from the syllabus.
          </div>
        </div>
      `;
    } else if (evidence && evidence.length > 0) {
      evidenceHTML = evidence.map((ev) => `
        <div class="evidence-card">
          <div class="evidence-header">
            <span class="evidence-citation">
              <span>📄 Page ${ev.page_number} Citation</span>
            </span>
            <span class="badge badge-neutral">${Math.round(ev.relevance_score * 100)}% Match</span>
          </div>
          <div class="evidence-quote">"${this.escapeHTML(ev.source_quote)}"</div>
        </div>
      `).join("");
    } else if (context_excerpt) {
      evidenceHTML = `
        <div class="evidence-card">
          <div class="evidence-header">
            <span class="evidence-citation"><span>📄 Syllabus Excerpt</span></span>
          </div>
          <div class="evidence-quote">"${this.escapeHTML(context_excerpt)}"</div>
        </div>
      `;
    }

    bubble.innerHTML = `
      <div class="chat-sender-header">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <span class="chat-sender-name">EduVerse Tutor</span>
          ${statusBadgeHTML}
        </div>
        <span style="font-size:0.7rem; color:var(--text-muted);">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div style="color:var(--text-primary); margin-top:0.25rem;">
        ${this.formatResponseText(answer)}
      </div>
      ${evidenceHTML}
    `;

    this.container.appendChild(bubble);
    this.scrollToBottom();
  }

  /**
   * Appends concept simplification card.
   */
  appendSimplification({ concept, analogy, key_points = [], syllabus_definition }) {
    if (!this.container) return;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble-tutor";

    const pointsListHTML = key_points
      .map((p) => `<li>${this.escapeHTML(p)}</li>`)
      .join("");

    bubble.innerHTML = `
      <div class="chat-sender-header">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <span class="chat-sender-name">Concept Simplifier</span>
          <span class="badge badge-teal">Pedagogical Analogy</span>
        </div>
        <span style="font-size:0.7rem; color:var(--text-muted);">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div class="simplify-card">
        <div class="simplify-title">
          <span>🧠</span> Real-World Mental Model for: "${this.escapeHTML(concept)}"
        </div>
        <p class="simplify-analogy">${this.escapeHTML(analogy)}</p>
        <div style="font-size:0.8rem; font-weight:700; color:var(--text-secondary); margin-bottom:0.35rem; text-transform:uppercase;">
          Core Key Takeaways:
        </div>
        <ul class="simplify-points">
          ${pointsListHTML}
        </ul>
        <div style="margin-top:0.6rem; padding-top:0.5rem; border-top:1px solid var(--border-subtle); font-size:0.78rem; color:var(--text-muted);">
          <strong>Formal Syllabus Definition:</strong> "${this.escapeHTML(syllabus_definition)}"
        </div>
      </div>
    `;

    this.container.appendChild(bubble);
    this.scrollToBottom();
  }

  /**
   * Appends an honest loading message.
   */
  appendLoading(text = "Synthesizing grounded explanation from notes…") {
    if (!this.container) return null;

    const loadingId = `loading-${Date.now()}`;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble-tutor";
    bubble.id = loadingId;
    bubble.innerHTML = `
      <div style="display:flex; align-items:center; gap:0.6rem; color:var(--text-secondary);">
        <div class="status-dot status-dot-pulse" style="background:var(--accent-teal);"></div>
        <span style="font-size:0.85rem;">${this.escapeHTML(text)}</span>
      </div>
    `;

    this.container.appendChild(bubble);
    this.scrollToBottom();
    return loadingId;
  }

  removeLoading(loadingId) {
    if (!loadingId) return;
    const el = document.getElementById(loadingId);
    if (el) el.remove();
  }

  scrollToBottom() {
    if (this.container) {
      this.container.scrollTop = this.container.scrollHeight;
    }
  }

  formatResponseText(text) {
    // Basic formatting for paragraphs and lists
    const escaped = this.escapeHTML(text);
    return escaped.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
  }

  escapeHTML(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}
