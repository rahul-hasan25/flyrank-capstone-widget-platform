import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.routers import admin, public, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables
    init_db()
    yield

app = FastAPI(
    title="Embeddable Widget & Lead-Capture Platform",
    description="A multi-tenant backend platform for managing, serving, and safely capturing leads via embeddable web widgets.",
    version="1.0.0",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS) Configuration
# External customer websites from any origin must be able to load config and submit leads
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["Cache-Control", "Retry-After"]
)

# Custom handler for versioned widget JavaScript delivery with production CDN cache headers
@app.get("/static/widget.v1.js")
async def serve_versioned_widget_script():
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "widget.v1.js")
    if not os.path.exists(script_path):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Widget script bundle not found.", "code": "ASSET_NOT_FOUND"}
        )
    return FileResponse(
        script_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Access-Control-Allow-Origin": "*"
        }
    )

# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Modular Routers
app.include_router(admin.router)
app.include_router(public.router)
app.include_router(dashboard.router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Widget Platform API",
        "environment": settings.ENVIRONMENT
    }

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard")
def dashboard_view():
    dash_path = os.path.join(static_dir, "dashboard.html")
    return FileResponse(dash_path, media_type="text/html")

# Consistent top-level JSON formatting for HTTP exceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    headers = exc.headers or {}
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": str(exc.detail), "code": "HTTP_ERROR"}
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Input validation error.", "code": "VALIDATION_ERROR", "details": exc.errors()}
    )

# Global Exception Handler for unhandled exceptions (never crash or leak 500 stack trace)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An internal server error occurred.",
            "code": "INTERNAL_SERVER_ERROR",
            "detail": str(exc) if settings.ENVIRONMENT == "development" else None
        }
    )
