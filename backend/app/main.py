
from fastapi import FastAPI
from sqlalchemy import text
import uvicorn

from app.core.dependencies import DbSession

app = FastAPI(title="CloudPilot")


@app.get("/health/db")
def health_db(db: DbSession):
    db.execute(text("SELECT 1"))
    return {"database": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
