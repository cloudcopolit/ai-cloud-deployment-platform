from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"


class GitHubError(Exception):
    pass


@dataclass
class GitHubProfile:
    github_id: str
    name: str
    email: str | None
    avatar_url: str | None


def build_authorize_url(state: str) -> str:
    query = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "read:user user:email",  # identity only, no repository access
        "state": state,
    })
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str) -> str:
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": settings.github_redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:  # GitHub returns 200 with an "error" field for a bad code
        raise GitHubError(data.get("error_description", "GitHub rejected the code"))
    return token


def fetch_profile(access_token: str) -> GitHubProfile:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(base_url=API_URL, headers=headers, timeout=10) as client:
        user = client.get("/user")
        user.raise_for_status()
        data = user.json()

        email = data.get("email")
        if not email:  # the email is hidden on the public profile
            emails = client.get("/user/emails")
            emails.raise_for_status()
            email = next(
                (e["email"] for e in emails.json() if e["primary"] and e["verified"]),
                None,
            )

    return GitHubProfile(
        github_id=str(data["id"]),  # the numeric id never changes; login names can
        name=data.get("name") or data["login"],
        email=email,
        avatar_url=data.get("avatar_url"),
    )