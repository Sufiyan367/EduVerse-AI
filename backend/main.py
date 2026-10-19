import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.routers import documents, tutor, quiz, health
from backend.services.storage_service import storage
from backend.schemas import DocumentUploadResponse

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="EduVerse AI — An Animated Virtual Tutor for Personalized Learning Backend REST API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(tutor.router)
app.include_router(quiz.router)

# Mount Images Directory for Institutional and Avatar Assets
images_dir = BASE_DIR / "EduVerse_AI_Project_Report" / "images"
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")

# Sample Document Endpoint for instant zero-setup demonstration
SAMPLE_ML_NOTES = """
COURSE SYLLABUS: ARTIFICIAL INTELLIGENCE & MACHINE LEARNING
DEPARTMENT OF ARTIFICIAL INTELLIGENCE & DATA SCIENCE, ICEM PUNE
UNIT IV: SUPERVISED LEARNING & LINEAR MODELS

1. INTRODUCTION TO SUPERVISED LEARNING
Supervised learning is a fundamental machine learning paradigm where an algorithm learns a mapping function f(X) -> Y from input features X to labeled target outputs Y. The training dataset consists of N input-output pairs D = {(x_1, y_1), (x_2, y_2), ..., (x_N, y_N)}. The objective is to minimize an empirical loss function over training instances while maintaining low generalization error on unseen test distributions.

2. CLASSIFICATION VERSUS REGRESSION
Supervised learning tasks are broadly divided based on the nature of the target variable Y:
- Regression: The target variable Y is continuous and real-valued (e.g., predicting student examination scores or housing valuation). Typical evaluation metrics include Mean Squared Error (MSE) and Mean Absolute Error (MAE).
- Classification: The target variable Y is discrete, assigning inputs to predefined categorical classes (e.g., binary pass/fail prediction or multi-class image recognition). Common metrics include accuracy, precision, recall, and F1-score.

3. LOGISTIC REGRESSION AND CROSS-ENTROPY LOSS
Despite its name, logistic regression is a linear classification model. It estimates the conditional probability P(Y=1|X) using the sigmoid logistic function:
sigma(z) = 1 / (1 + exp(-z)), where z = w^T * x + b.
The optimization parameter vector w is trained by minimizing the Binary Cross-Entropy (Log Loss) function:
J(w) = - (1/N) * sum_{i=1}^N [ y_i * log(y_hat_i) + (1 - y_i) * log(1 - y_hat_i) ].
Unlike Mean Squared Error, cross-entropy produces a smooth, convex optimization surface for logistic regression, ensuring that gradient descent converges toward the global optimum without getting trapped in local minima.

4. OVERFITTING, UNDERFITTING, AND REGULARIZATION
- Overfitting: Occurs when a high-capacity model learns idiosyncratic noise and random fluctuations in the training data rather than underlying patterns. An overfitted model exhibits low training error but high test error (high variance).
- Underfitting: Occurs when a model is overly simplistic and cannot capture fundamental relationships (high bias).
- Regularization: Prevents overfitting by penalizing excessively large weight magnitudes. L2 regularization (Ridge) adds the squared norm ||w||_2^2, shrinking weights toward zero, while L1 regularization (Lasso) adds the absolute norm ||w||_1, encouraging sparsity and feature selection.

5. GRADIENT DESCENT OPTIMIZATION
Gradient descent is an iterative first-order optimization algorithm that updates model parameters in the direction opposite to the gradient of the loss function:
w := w - alpha * grad_w J(w),
where alpha denotes the learning rate hyperparameter. Selecting an excessively large learning rate causes divergence, whereas a tiny learning rate leads to slow convergence.
"""

@app.post("/api/documents/sample", response_model=DocumentUploadResponse, tags=["Documents"])
async def load_sample_document():
    """Loads built-in Machine Learning syllabus notes for immediate testing."""
    pages = [
        {"page_number": 1, "text": SAMPLE_ML_NOTES[:1500], "char_count": 1500},
        {"page_number": 2, "text": SAMPLE_ML_NOTES[1500:], "char_count": len(SAMPLE_ML_NOTES) - 1500}
    ]
    doc_id = storage.store_document(
        filename="Unit4_SupervisedLearning_ICEM.pdf",
        pages_data=pages,
        raw_text=SAMPLE_ML_NOTES.strip()
    )
    return DocumentUploadResponse(
        doc_id=doc_id,
        filename="Unit4_SupervisedLearning_ICEM.pdf",
        pages=2,
        char_count=len(SAMPLE_ML_NOTES.strip()),
        preview=SAMPLE_ML_NOTES.strip()[:350] + "...",
        status="ready",
        message="Loaded verified Machine Learning syllabus sample notes."
    )

# Serve Frontend SPA
@app.get("/", tags=["Frontend"])
async def serve_frontend():
    frontend_path = BASE_DIR / "frontend" / "index.html"
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(str(frontend_path))
