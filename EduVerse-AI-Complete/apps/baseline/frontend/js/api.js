/**
 * EduVerse AI — Centralized API Client Module
 * Provides typed, error-handled HTTP requests to the FastAPI backend.
 */

const API_BASE = "";

class APIError extends Error {
  constructor(message, status = 500, details = null) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.details = details;
  }
}

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
    const res = await fetch(`${API_BASE}/api/health`);
    return handleResponse(res);
  },

  /**
   * Uploads a user PDF document.
   */
  async uploadPDF(file) {
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
    const res = await fetch(`${API_BASE}/api/documents/sample`, {
      method: "POST",
    });
    return handleResponse(res);
  },

  /**
   * Lists all uploaded and active documents.
   */
  async listDocuments() {
    const res = await fetch(`${API_BASE}/api/documents`);
    return handleResponse(res);
  },

  /**
   * Fetches specific page passage text with valid metadata.
   */
  async getPassage(docId, page = 1) {
    const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}/passage?page=${page}`);
    return handleResponse(res);
  },

  /**
   * Retrieves or generates the Knowledge Constellation concept graph.
   */
  async getConcepts(docId) {
    const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}/concepts`);
    return handleResponse(res);
  },

  /**
   * Submits a student query grounded in the specified document.
   */
  async queryTutor(docId, query, mode = "standard") {
    const res = await fetch(`${API_BASE}/api/tutor/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, query, mode }),
    });
    return handleResponse(res);
  },

  /**
   * Decomposes a concept into an intuitive analogy and key points.
   */
  async simplifyConcept(docId, concept) {
    const res = await fetch(`${API_BASE}/api/tutor/simplify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, concept }),
    });
    return handleResponse(res);
  },

  /**
   * Generates active recall MCQs grounded in the document.
   */
  async generateQuiz(docId, count = 3) {
    const res = await fetch(`${API_BASE}/api/quiz/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, count }),
    });
    return handleResponse(res);
  },

  /**
   * Evaluates student quiz answers and saves score to SQLite.
   */
  async evaluateQuiz(quizId, answers) {
    const res = await fetch(`${API_BASE}/api/quiz/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_id: quizId, answers }),
    });
    return handleResponse(res);
  },

  /**
   * Retrieves genuine persisted assessment history from SQLite.
   */
  async getAssessmentHistory(docId = null) {
    let url = `${API_BASE}/api/quiz/history`;
    if (docId) {
      url += `?doc_id=${encodeURIComponent(docId)}`;
    }
    const res = await fetch(url);
    return handleResponse(res);
  },
};
