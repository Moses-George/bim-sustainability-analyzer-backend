import logging

from app.api import auth, chat, energy, ifc, materials, projects
from app.models import material, project
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import recommendations
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="BIM Sustainability Analyzer API", version="1.0.0")

origins = (
    [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    if settings.CORS_ORIGINS
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(energy.router, prefix="/api/energy", tags=["energy"])
app.include_router(materials.router, prefix="/api/materials", tags=["materials"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["ai"])
app.include_router(chat.router, prefix="/api/chat", tags=["ai"])
app.include_router(ifc.router, prefix="/api/ifc", tags=["ifc"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "bim-sustainability-analyzer"}


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
