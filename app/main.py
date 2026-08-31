from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import ArchitectureAnalysis
from app.services.llm import analyze_repository
from app.services.repository import read_zip_repository


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Code Architect V0",
    version="0.1.0",
    description="Upload a codebase ZIP and generate a structured architecture analysis.",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze", response_model=ArchitectureAnalysis)
async def analyze(
    repository: UploadFile = File(...),
    prompt: str = Form(""),
):
    filename = repository.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip repository.")

    try:
        data = await repository.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="ZIP must be 25 MB or smaller.")

        snapshot = read_zip_repository(data)
        return analyze_repository(snapshot.to_prompt_text(), prompt)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {type(exc).__name__}: {exc}",
        ) from exc
