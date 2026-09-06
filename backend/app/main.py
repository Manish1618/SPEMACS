from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.models.database import engine, Base, SessionLocal, run_migrations
from app.services.ingestion import seed_database_and_graph
from app.api import auth, cases, graph, map_timeline, evidence, ai, osint, ingestion, cross_case, users, audit

# Alembic owns the schema. Upgrading here means a fresh database is usable
# immediately and an existing one is never left a revision behind.
run_migrations()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="SPEMASS: Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures"
)

# CORS is an explicit origin list: credentialed requests (the refresh cookie)
# cannot be combined with a wildcard origin, and should not be.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.CSRF_HEADER_NAME],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(cases.router, prefix=settings.API_V1_STR)
app.include_router(graph.router, prefix=settings.API_V1_STR)
app.include_router(map_timeline.router, prefix=settings.API_V1_STR)
app.include_router(evidence.router, prefix=settings.API_V1_STR)
app.include_router(ai.router, prefix=settings.API_V1_STR)
app.include_router(osint.router, prefix=settings.API_V1_STR)
app.include_router(ingestion.router, prefix=settings.API_V1_STR)
app.include_router(cross_case.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        seed_database_and_graph(db)
    finally:
        db.close()

@app.get("/")
def root():
    return {
        "system": "SPEMASS Decision-Support Platform",
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "version": settings.VERSION,
        "demo_mode": settings.DEMO_MODE
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
