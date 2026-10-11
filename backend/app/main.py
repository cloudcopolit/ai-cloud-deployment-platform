
from fastapi import FastAPI
from sqlalchemy import text

from app.api.router import api_router
from app.core.dependencies import DbSession
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(title="CloudPilot")

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],  # an exact origin, never "*" with credentials
    allow_credentials=True,                 # lets the browser send the cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health/db")
def health_db(db: DbSession):
    db.execute(text("SELECT 1"))
    return {"database": "ok"}



