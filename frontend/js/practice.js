/**
 * EduVerse AI — Document-Level Practice & Assessment Module
 * Manages quiz synthesis, answer submission, rationale review, and persisted SQLite history.
 */

export class PracticeManager {
  constructor(containerId, historyContainerId, { onGenerate, onSubmit, onFetchHistory }) {
    this.container = document.getElementById(containerId);
    this.historyContainer = document.getElementById(historyContainerId);
    this.onGenerate = onGenerate;
    this.onSubmit = onSubmit;
    this.onFetchHistory = onFetchHistory;

    this.currentQuiz = null;
    this.userAnswers = new Map(); // question_id -> selected_index
    this.isEvaluated = false;
  }

  /**
   * Sets new quiz questions and resets selection state.
   */
  setQuiz(quizData) {
    this.currentQuiz = quizData;
    this.userAnswers.clear();
    this.isEvaluated = false;
    this.renderQuiz();
  }

  /**
   * Renders the interactive quiz questions and submit button.
   */
  renderQuiz() {
    if (!this.container) return;

    if (!this.currentQuiz || !this.currentQuiz.questions || this.currentQuiz.questions.length === 0) {
      this.container.innerHTML = `
        <div class="empty-state">
          <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <p class="empty-state-title">No Active Quiz</p>
          <p class="empty-state-desc">Generate active recall questions grounded in your selected syllabus document.</p>
          <button class="btn btn-primary" id="btn-start-quiz">
            <span>⚡</span> Generate Practice Quiz
          </button>
        </div>
      `;

      const btn = document.getElementById("btn-start-quiz");
      if (btn && this.onGenerate) {
        btn.addEventListener("click", () => this.onGenerate());
      }
      return;
    }

    const { questions, quiz_id } = this.currentQuiz;

    let html = `
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
        <span class="input-label">Document Assessment (${questions.length} Questions)</span>
        <span class="badge badge-teal">Active Recall</span>
      </div>
    `;

    questions.forEach((q, idx) => {
      const selectedIndex = this.userAnswers.get(q.question_id);

      html += `
        <div class="quiz-card" id="quiz-card-${q.question_id}">
          <div class="quiz-question-title">
            <span style="color:var(--accent-teal); font-weight:700;">Q${idx + 1}.</span> ${this.escapeHTML(q.question_text)}
          </div>
          <div class="quiz-options-list" role="radiogroup" aria-label="Question ${idx + 1} options">
      `;

      const optionLetters = ["A", "B", "C", "D", "E"];

      q.options.forEach((optText, optIdx) => {
        const isSelected = selectedIndex === optIdx;
        const letter = optionLetters[optIdx] || (optIdx + 1);

        html += `
          <button 
            type="button"
            class="quiz-option-card ${isSelected ? 'selected' : ''}" 
            data-qid="${q.question_id}" 
            data-optidx="${optIdx}"
            role="radio"
            aria-checked="${isSelected}"
            tabindex="0"
          >
            <div class="quiz-option-indicator">${letter}</div>
            <div style="font-size:0.88rem; color:var(--text-primary); line-height:1.4;">${this.escapeHTML(optText)}</div>
          </button>
        `;
      });

      html += `
          </div>
        </div>
      `;
    });

    html += `
      <div style="margin-top:1rem; display:flex; flex-direction:column; gap:0.5rem;">
        <button class="btn btn-primary" id="btn-submit-assessment" style="width:100%;">
          <span>✓</span> Submit & Score Assessment
        </button>
        <button class="btn btn-ghost btn-sm" id="btn-regenerate-quiz" style="width:100%;">
          <span>🔄</span> Generate New Set
        </button>
      </div>
    `;

    this.container.innerHTML = html;

    // Attach click & keyboard listeners to option buttons
    this.container.querySelectorAll(".quiz-option-card").forEach((optBtn) => {
      const qid = parseInt(optBtn.getAttribute("data-qid"), 10);
      const optIdx = parseInt(optBtn.getAttribute("data-optidx"), 10);

      const selectHandler = () => {
        if (this.isEvaluated) return;
        this.userAnswers.set(qid, optIdx);
        this.renderQuiz();
      };

      optBtn.addEventListener("click", selectHandler);
    });

    // Attach submit listener
    const submitBtn = document.getElementById("btn-submit-assessment");
    if (submitBtn && this.onSubmit) {
      submitBtn.addEventListener("click", () => {
        if (this.userAnswers.size < questions.length) {
          const unanswered = questions.length - this.userAnswers.size;
          if (!confirm(`You have ${unanswered} unanswered question(s). Submit anyway?`)) {
            return;
          }
        }

        const submission = [];
        this.userAnswers.forEach((selectedIdx, qid) => {
          submission.push({
            question_id: qid,
            selected_option_index: selectedIdx,
          });
        });

        this.onSubmit(quiz_id, submission);
      });
    }

    // Attach regenerate listener
    const regenBtn = document.getElementById("btn-regenerate-quiz");
    if (regenBtn && this.onGenerate) {
      regenBtn.addEventListener("click", () => this.onGenerate());
    }
  }

  /**
   * Displays evaluation results with score banner, rationales, and correct answers.
   */
  showEvaluation(result) {
    this.isEvaluated = true;
    if (!this.container) return;

    const { score_percentage, correct_count, total_questions, passed, breakdown, feedback_message } = result;

    let html = `
      <div class="assessment-score-banner">
        <div class="score-big-number">${score_percentage}%</div>
        <div style="font-size:0.95rem; font-weight:700; color:${passed ? 'var(--status-success)' : 'var(--status-danger)'}; margin-bottom:0.35rem;">
          ${passed ? '✓ Passing Comprehension' : '⚠️ Revision Recommended'}
        </div>
        <div style="font-size:0.8rem; color:var(--text-secondary); line-height:1.4;">
          ${this.escapeHTML(feedback_message)}
        </div>
        <div style="margin-top:0.6rem;">
          <span class="badge ${passed ? 'badge-success' : 'badge-danger'}">
            ${correct_count} of ${total_questions} Correct
          </span>
        </div>
      </div>
      <div style="margin-top:1rem; margin-bottom:0.5rem;" class="input-label">Detailed Question Breakdown</div>
    `;

    breakdown.forEach((item, idx) => {
      html += `
        <div class="quiz-card" style="border-left: 3px solid ${item.is_correct ? 'var(--status-success)' : 'var(--status-danger)'};">
          <div class="quiz-question-title">
            <span style="color:${item.is_correct ? 'var(--status-success)' : 'var(--status-danger)'}; font-weight:700;">
              ${item.is_correct ? '✓' : '✗'} Q${idx + 1}.
            </span> 
            ${this.escapeHTML(item.question_text)}
          </div>
          <div style="font-size:0.82rem; margin-top:0.25rem;">
            <div style="color:${item.is_correct ? 'var(--status-success)' : 'var(--status-danger)'};">
              Your Answer: Option ${item.selected_option_index >= 0 ? ['A', 'B', 'C', 'D'][item.selected_option_index] : 'None'}
            </div>
            ${!item.is_correct ? `
              <div style="color:var(--status-success); font-weight:600; margin-top:2px;">
                Correct Answer: Option ${['A', 'B', 'C', 'D'][item.correct_option_index]}
              </div>
            ` : ''}
          </div>
          <div class="quiz-rationale-box">
            <strong style="color:var(--text-primary);">Pedagogical Rationale:</strong> ${this.escapeHTML(item.rationale)}
          </div>
        </div>
      `;
    });

    html += `
      <div style="margin-top:1rem;">
        <button class="btn btn-primary" id="btn-next-quiz" style="width:100%;">
          <span>⚡</span> Try Another Practice Set
        </button>
      </div>
    `;

    this.container.innerHTML = html;

    const nextBtn = document.getElementById("btn-next-quiz");
    if (nextBtn && this.onGenerate) {
      nextBtn.addEventListener("click", () => this.onGenerate());
    }
  }

  /**
   * Renders genuine persisted assessment history directly from SQLite.
   */
  renderHistory(historyData) {
    if (!this.historyContainer) return;

    if (!historyData || !historyData.history || historyData.history.length === 0) {
      this.historyContainer.innerHTML = `
        <div class="empty-state">
          <p class="empty-state-title">No Prior Assessments</p>
          <p class="empty-state-desc">Complete a quiz to record genuine progress in the SQLite database.</p>
        </div>
      `;
      return;
    }

    const { history, total_assessments, average_score } = historyData;

    let html = `
      <div style="background:var(--bg-surface-raised); border-radius:var(--radius-sm); padding:var(--space-md); border:1px solid var(--border-subtle); margin-bottom:1rem;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Assessments Recorded</div>
            <div style="font-size:1.4rem; font-weight:800; color:var(--text-primary);">${total_assessments}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Cumulative Avg Score</div>
            <div style="font-size:1.4rem; font-weight:800; color:var(--accent-teal); font-family:var(--font-mono);">${average_score}%</div>
          </div>
        </div>
      </div>
      <div class="input-label" style="margin-bottom:0.5rem;">Evaluation Timeline (SQLite Persisted)</div>
      <div style="display:flex; flex-direction:column; gap:0.5rem;">
    `;

    history.forEach((h) => {
      const isPass = h.passed;
      html += `
        <div class="history-item">
          <div class="history-meta">
            <span class="history-filename">${this.escapeHTML(h.filename)}</span>
            <span class="history-date">${this.escapeHTML(h.evaluated_at)} • ${h.correct_count}/${h.total_questions} correct</span>
          </div>
          <div class="history-score">
            <span class="history-score-val" style="color:${isPass ? 'var(--status-success)' : 'var(--status-danger)'};">
              ${h.score_percentage}%
            </span>
            <span class="badge ${isPass ? 'badge-success' : 'badge-danger'}">
              ${isPass ? 'PASS' : 'REVIEW'}
            </span>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    this.historyContainer.innerHTML = html;
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
