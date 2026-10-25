from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.core.dependencies import DbSession
from app.core.errors import (
    CloudPilotError,
    handle_cloudpilot_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)
from app.core.logging import RequestIDMiddleware, configure_logging
from app.core.middleware import OriginSecurityMiddleware

configure_logging()

app = FastAPI(title="CloudPilot")

app.add_middleware(RequestIDMiddleware)
app.add_middleware(OriginSecurityMiddleware)
app.add_exception_handler(CloudPilotError, handle_cloudpilot_error)
app.add_exception_handler(StarletteHTTPException, handle_http_exception)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(Exception, handle_unexpected_error)

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],  # an exact origin, never "*" with credentials
    allow_credentials=True,  # lets the browser send the cookie
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health/db")
def health_db(db: DbSession):
    db.execute(text("SELECT 1"))
    return {"database": "ok"}
