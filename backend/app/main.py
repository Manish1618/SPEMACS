from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.models.database import engine, Base, SessionLocal
from app.services.ingestion import seed_database_and_graph
from app.api import auth, cases, graph, map_timeline, evidence, ai, osint, ingestion

# Create DB Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="SPEMASS: Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
