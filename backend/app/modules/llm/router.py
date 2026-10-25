from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app.integrations.llm import provider_status
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["llm"])


@router.get("/llm/providers")
def get_llm_providers(_: CurrentUser, refresh: bool = False) -> list[dict[str, Any]]:
    """Which language-model providers are REAL or MOCKED-ONLY, whether they answer, and the
    model the selection policy picks. Never includes keys. Cached for 10 minutes."""
    return [asdict(row) for row in provider_status(refresh=refresh)]
