import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import ArchitectureAnalysis, DeveloperIntent, IntakeResponse
from app.services.intent import build_intake, merge_intent, missing_required_fields
from app.services.llm import analyze_repository
from app.services.repository import read_zip_repository


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Code Architect Adaptive",
    version="0.3.0",
    description="Conditional clarification + LLM routing + quality-aware cascading.",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.3.0", "routing": True, "cascading": True}


@app.post("/api/intake", response_model=IntakeResponse)
async def intake(prompt: str = Form(""), answers_json: str = Form("{}")):
    try:
        answers = json.loads(answers_json or "{}")
        return build_intake(prompt, answers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="answers_json must be valid JSON.") from exc


@app.post("/api/analyze", response_model=ArchitectureAnalysis)
async def analyze(
    repository: UploadFile = File(...),
    prompt: str = Form(""),
    intent_json: str = Form("{}"),
    routing_mode: str = Form("auto"),
):
    if not (repository.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip repository.")
    if routing_mode not in {"auto", "cheap", "strong"}:
        raise HTTPException(status_code=400, detail="routing_mode must be auto, cheap, or strong.")

    try:
        data = await repository.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="ZIP must be 25 MB or smaller.")

        snapshot = read_zip_repository(data)
        base = build_intake(prompt).intent
        supplied = json.loads(intent_json or "{}")
        intent = merge_intent(base, supplied)
        missing = missing_required_fields(intent)
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"message": "More developer intent is required before analysis.", "missing_fields": missing},
            )

        return analyze_repository(snapshot.to_prompt_text(), intent, routing_mode)
    except HTTPException:
        raise
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="intent_json must be valid JSON.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}: {exc}") from exc
