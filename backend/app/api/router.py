from fastapi import APIRouter

from app.modules.analysis.router import router as analysis_router
from app.modules.architectures.router import router as architectures_router
from app.modules.auth.router import router as auth_router
from app.modules.deployments.router import router as deployments_router
from app.modules.projects.router import router as projects_router
from app.modules.repositories.router import router as repositories_router
from app.modules.teams.router import router as teams_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(teams_router)
api_router.include_router(projects_router)
api_router.include_router(repositories_router)
api_router.include_router(analysis_router)
api_router.include_router(architectures_router)
api_router.include_router(deployments_router)
