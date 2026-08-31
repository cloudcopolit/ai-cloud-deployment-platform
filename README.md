# Code Architect V0

A deliberately small prototype for:

**repository ZIP + user goal → LLM architecture analysis → structured JSON → Mermaid diagram**

The goal of V0 is to validate the core experience before adding GitHub, AST/static analysis,
RAG, AWS discovery, Terraform, or deployment automation.

## What V0 does

- Uploads a `.zip` codebase.
- Filters obvious generated/binary directories and files.
- Builds a bounded repository snapshot.
- Sends repository evidence + the user's goal through OpenRouter's free-model API route.
- Requires a structured architecture result.
- Generates Mermaid from the structured result instead of trusting model-generated diagram text.
- Shows detected stack, components, evidence, recommendations, assumptions, and raw JSON.

## Architecture

```text
Browser
  |
  v
FastAPI
  |
  +--> ZIP reader / repository snapshot
  |
  +--> OpenAI Responses API
          |
          v
  ArchitectureAnalysis JSON
          |
          +--> deterministic Mermaid generator
          |
          v
        Browser
```

## Setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set:

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/free
```

Then run:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Docker

```bash
cp .env.example .env
# edit .env

docker compose up --build
```

## Test

```bash
pytest -q
```

The tests do not call the LLM API.

## Cost

V0 defaults to `openrouter/free`, which routes requests to currently available free models. Token price is $0, but free endpoints are rate-limited and availability can change. No paid model is required for this prototype.

## Try the included sample

A tiny sample repository is included under `sample_repo/`.
Zip it:

```bash
cd sample_repo
zip -r ../sample_repo.zip .
cd ..
```

Then upload `sample_repo.zip` through the UI.

## V0 limitations

This is intentionally a prototype.

1. The codebase is summarized as bounded text; there is no AST/static-analysis engine yet.
2. There is no RAG/vector database.
3. Large repositories will be truncated.
4. The app does not clone private GitHub repositories.
5. It does not inspect an AWS account or deploy infrastructure.
6. It does not execute uploaded code.
7. Architecture inference can still be wrong; `evidence` and `assumptions` are included so you can evaluate that.

## Strong V1 path

Keep the `ArchitectureAnalysis` schema and replace/improve the evidence engine:

```text
ZIP/GitHub
   |
   +--> manifests/config parser
   +--> Tree-sitter AST analysis
   +--> dependency graph
   +--> route/API extraction
   +--> DB/entity extraction
   +--> targeted RAG
              |
              v
       ArchitectureAnalysis
              |
        same UI contract
```

After V1 is reliable, add:

1. GitHub App/OAuth and repository sync.
2. Architecture history by commit.
3. Current-vs-proposed architecture diff.
4. AWS architecture recommendation.
5. Terraform generation.
6. `terraform validate` + `terraform plan`.
7. Explicit human approval before any apply/deployment.
