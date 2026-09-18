# Code Architect V0.3 — Adaptive Routing + Cascading

This prototype analyzes an uploaded repository while minimizing unnecessary LLM cost.

## Core flow

```text
Repository + developer prompt
        |
        v
Deterministic intent extraction
        |
        +--> enough information --------+
        |                               |
        +--> missing goal/depth         |
                 |                      |
                 v                      |
          conditional MCQs              |
                 |                      |
                 +----------------------+
                                        v
                               structured developer intent
                                        |
                                        v
                                zero-cost pre-router
                                  /             \
                           obvious hard       cheap-first
                               |                  |
                               v                  v
                           strong LLM          cheap LLM
                                                  |
                                                  v
                                       deterministic evaluator
                                            /          \
                                         pass          fail
                                          |             |
                                          v             v
                                        return       strong LLM
```

The current heuristic pre-router is intentionally retained as an experimental baseline. Auto mode adds a quality-aware cascade after cheap inference.

## Conditional clarification

Only `goal` and `depth` are required. If they can be extracted from the developer's free-text request, no questionnaire is shown. If one or both are missing, the UI asks only those missing MCQs and supports **Other** with free text.

## Modes

- `Auto`: hybrid routing + cascading.
- `Cheap-only`: experimental baseline; never escalates.
- `Strong-only`: experimental baseline; skips cheap inference.

## Configuration

Create `.env`:

```env
OPENROUTER_API_KEY=your_key_here
CHEAP_MODEL=openrouter/free
STRONG_MODEL=openai/gpt-4o
ROUTING_THRESHOLD=5
QUALITY_THRESHOLD=0.78
MAX_FILES=80
MAX_FILE_CHARS=12000
MAX_REPO_CHARS=180000
MAX_OUTPUT_TOKENS=3000
```

If OpenRouter reports a 402 because your credit limit cannot reserve 3000 output tokens, reduce `MAX_OUTPUT_TOKENS` to `2000` or `1500`.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
pytest -q
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Main modules

- `app/services/intent.py` — zero-cost structured intent extraction and conditional MCQs.
- `app/services/prompt_builder.py` — builds a normalized evidence-first analysis prompt.
- `app/services/router.py` — pre-inference routing baseline.
- `app/services/evaluator.py` — deterministic cheap-result quality scoring.
- `app/services/llm.py` — hybrid routing/cascade orchestration and OpenRouter calls.
- `app/services/repository.py` — bounded repository snapshot.
- `app/services/mermaid.py` — deterministic Mermaid generation.

## Research direction

The UI returns a trace containing initial route/model, pre-route score, cheap-result quality metrics, escalation decision, and final model. This makes it possible to compare cheap-only, strong-only, heuristic routing, cascade, and hybrid routing+cascade on cost, latency, escalation rate, and architecture-analysis quality.
