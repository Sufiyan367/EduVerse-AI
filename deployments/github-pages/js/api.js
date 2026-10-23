/**
 * EduVerse AI — Centralized API Client Module (GitHub Pages Static Preview Edition)
 * Provides typed, error-handled requests with graceful fallback for static GitHub Pages hosting.
 */

const IS_GITHUB_PAGES = typeof window !== "undefined" && (
  window.location.hostname.endsWith("github.io") || 
  window.location.protocol === "file:" ||
  window.location.search.includes("preview=true")
);

const API_BASE = "";

class APIError extends Error {
  constructor(message, status = 500, details = null) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.details = details;
  }
}

// Verified Curriculum Demo Fixtures for Static Preview Mode
const PREVIEW_DOCS = [
  {
    doc_id: "preview_ml_syllabus_icem",
    filename: "Unit4_SupervisedLearning_ICEM.pdf",
    total_pages: 18,
    status: "ready",
    uploaded_at: new Date().toISOString()
  }
];

const PREVIEW_CONCEPTS = [
  { id: "c1", label: "Supervised Learning", category: "Core Theory", page: 1, connections: ["c2", "c3", "c4"] },
  { id: "c2", label: "Linear Regression", category: "Algorithms", page: 3, connections: ["c1", "c5"] },
  { id: "c3", label: "Logistic Regression", category: "Algorithms", page: 6, connections: ["c1", "c5"] },
  { id: "c4", label: "Support Vector Machines", category: "Algorithms", page: 10, connections: ["c1", "c6"] },
  { id: "c5", label: "Cost Functions & MSE", category: "Mathematics", page: 4, connections: ["c2", "c3"] },
  { id: "c6", label: "Kernel Trick & Non-Linearity", category: "Mathematics", page: 12, connections: ["c4"] }
];

const PREVIEW_QUIZ = {
  quiz_id: "preview_quiz_supervised",
  questions: [
    {
      id: "q1",
      question: "Which cost function is strictly convex and guarantees global convergence in Linear Regression?",
      options: ["Mean Squared Error (MSE)", "Cross-Entropy Loss", "Hinge Loss", "Kullback-Leibler Divergence"],
      correct_index: 0,
      explanation: "Mean Squared Error (MSE) creates a strictly convex parabolic error bowl for linear models, ensuring no local minima entrap gradient descent."
    },
    {
      id: "q2",
      question: "In Logistic Regression, which activation function maps real-valued outputs to probability domain [0, 1]?",
      options: ["Sigmoid / Logistic Function", "Rectified Linear Unit (ReLU)", "Softplus", "Leaky ReLU"],
      correct_index: 0,
      explanation: "The sigmoid function 1 / (1 + e^-z) maps any input from (-infinity, +infinity) strictly into the probability range (0, 1)."
    }
  ]
};

async function handleResponse(response) {
  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
    let details = null;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorMessage = typeof errorJson.detail === "string" 
          ? errorJson.detail 
          : JSON.stringify(errorJson.detail);
      }
      details = errorJson;
    } catch {
      // response wasn't JSON
    }
    throw new APIError(errorMessage, response.status, details);
  }
  return await response.json();
}

export const api = {
  /**
   * Checks backend health and SQLite connection status.
   */
  async getHealth() {
    if (IS_GITHUB_PAGES) {
      return {
        status: "static_preview",
        project: "EduVerse AI (GitHub Pages Preview)",
        version: "1.0.0",
        active_documents: 1,
        preview_mode: true
      };
    }
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      return await handleResponse(res);
    } catch {
      return {
        status: "static_preview",
        project: "EduVerse AI (Offline Preview)",
        version: "1.0.0",
        active_documents: 1,
        preview_mode: true
      };
    }
  },

  /**
   * Uploads a user PDF document.
   */
  async uploadPDF(file) {
    if (IS_GITHUB_PAGES) {
      throw new APIError(
        "PDF ingestion and PyMuPDF text extraction require the local Python FastAPI backend. Run 'run_eduverse.ps1' locally to upload custom documents.",
        400
      );
    }
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/documents/upload`, {
      method: "POST",
      body: formData,
    });
    return handleResponse(res);
  },

  /**
   * Loads verified ML Syllabus sample notes for instant demonstration.
   */
  async loadSampleNotes() {
    if (IS_GITHUB_PAGES) {
      return PREVIEW_DOCS[0];
    }
    try {
      const res = await fetch(`${API_BASE}/api/documents/sample`, {
        method: "POST",
      });
      return await handleResponse(res);
    } catch {
      return PREVIEW_DOCS[0];
    }
  },

  /**
   * Lists all uploaded and active documents.
   */
  async listDocuments() {
    if (IS_GITHUB_PAGES) {
      return PREVIEW_DOCS;
    }
    try {
      const res = await fetch(`${API_BASE}/api/documents`);
      return await handleResponse(res);
    } catch {
      return PREVIEW_DOCS;
    }
  },

  /**
   * Fetches specific page passage text with valid metadata.
   */
  async getPassage(docId, page = 1) {
    if (IS_GITHUB_PAGES) {
      return {
        doc_id: docId,
        page: page,
        text: `Department of AI & Data Science, ICEM Pune — Unit IV: Supervised Learning & Optimization.\nPage ${page}: Concepts include linear regression cost function minimization, gradient descent derivations, logistic classification thresholds, and maximum-margin hyperplane formulation in Support Vector Machines.`
      };
    }
    try {
      const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}/passage?page=${page}`);
      return await handleResponse(res);
    } catch {
      return {
        doc_id: docId,
        page: page,
        text: "Curriculum segment active in static preview mode."
      };
    }
  },

  /**
   * Retrieves or generates the Knowledge Constellation concept graph.
   */
  async getConcepts(docId) {
    if (IS_GITHUB_PAGES) {
      return PREVIEW_CONCEPTS;
    }
    try {
      const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}/concepts`);
      return await handleResponse(res);
    } catch {
      return PREVIEW_CONCEPTS;
    }
  },

  /**
   * Submits a student query grounded in the specified document.
   */
  async queryTutor(docId, query, mode = "standard") {
    if (IS_GITHUB_PAGES) {
      throw new APIError(
        "Live AI Tutor generation requires the local Python FastAPI backend with Gemini or Ollama credentials. Run 'run_eduverse.ps1' locally to query the tutor.",
        400
      );
    }
    const res = await fetch(`${API_BASE}/api/tutor/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, query, mode }),
    });
    return handleResponse(res);
  },

  /**
   * Generates a grounded quiz for active document.
   */
  async generateQuiz(docId) {
    if (IS_GITHUB_PAGES) {
      return PREVIEW_QUIZ;
    }
    try {
      const res = await fetch(`${API_BASE}/api/quiz/generate?doc_id=${encodeURIComponent(docId)}`);
      return await handleResponse(res);
    } catch {
      return PREVIEW_QUIZ;
    }
  },

  /**
   * Submits student answers for evaluation.
   */
  async submitQuiz(quizId, answers) {
    if (IS_GITHUB_PAGES) {
      // In static preview mode, evaluate against preview quiz client-side without claiming DB persistence
      const questions = PREVIEW_QUIZ.questions;
      let score = 0;
      const feedback = questions.map((q) => {
        const studentAns = answers[q.id];
        const isCorrect = studentAns === q.correct_index;
        if (isCorrect) score += 1;
        return {
          question_id: q.id,
          is_correct: isCorrect,
          explanation: q.explanation,
        };
      });
      return {
        quiz_id: quizId,
        score: score,
        total: questions.length,
        percentage: Math.round((score / questions.length) * 100),
        feedback: feedback,
        persisted: false,
        note: "Preview evaluation completed. Database persistence requires running the local backend."
      };
    }
    const res = await fetch(`${API_BASE}/api/quiz/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_id: quizId, answers }),
    });
    return handleResponse(res);
  },

  /**
   * Retrieves historical evaluations.
   */
  async getEvaluationHistory(docId) {
    if (IS_GITHUB_PAGES) {
      return [];
    }
    try {
      const res = await fetch(`${API_BASE}/api/evaluations?doc_id=${encodeURIComponent(docId)}`);
      return await handleResponse(res);
    } catch {
      return [];
    }
  },

  /**
   * Resets active session.
   */
  async resetWorkspace() {
    if (IS_GITHUB_PAGES) {
      return { status: "reset_preview" };
    }
    const res = await fetch(`${API_BASE}/api/workspace/reset`, { method: "POST" });
    return handleResponse(res);
  }
};
