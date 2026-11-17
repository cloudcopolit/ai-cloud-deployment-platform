# Project API Reference

This document describes the backend APIs exposed by the project. It focuses on the real routes registered in the application and explains prerequisites, inputs, example payloads, outputs, and business logic for each endpoint.

## 1. API Overview

The backend is organized by module and mounted through the main API router:

- Auth
- Teams
- Projects
- Repositories
- Analysis
- Architectures
- Deployments
- Webhooks
- LLM
- System health

## 2. Common Rules and Prerequisites

### Authentication
Most endpoints require an authenticated user via the `CurrentUser` dependency. Browser clients use secure cookies; API clients can also pass the access token in the Authorization flow if enabled by the frontend or client setup.

### Authorization assumptions
- Team membership is required for most team/project operations.
- Project access is scoped to its parent team and user permissions.
- Deployment approval actions normally require an admin or owner-level role.
- GitHub repository actions require the repository to be connected to the correct project.

### Request conventions
- IDs are UUID values.
- JSON request bodies are validated by Pydantic.
- Many create/update endpoints return a `201` or `202` response.
- Async analysis endpoints return `202 Accepted` and should be polled until terminal state.

### Public endpoints
The public or externally callable endpoints are:
- `GET /auth/github/login`
- `GET /auth/github/callback`
- `POST /auth/dev-login` (development only)
- `POST /webhooks/github` (GitHub signature validated)
- `GET /health/db`
- `GET /llm/providers` requires auth

## 3. Endpoint-by-Endpoint Details

## 3.1 Auth API

### GET /auth/github/login

- Prerequisites:
  - No login required.
  - Browser must be able to receive redirect.
- Request body:
  - None.
- Example request:
  ```http
  GET /auth/github/login
  ```
- Example response:
  - Redirect to GitHub OAuth authorize URL.
- Business logic:
  - Generates a random OAuth state.
  - Stores the state in a secure cookie.
  - Redirects the user to the GitHub login flow.

### GET /auth/github/callback

- Prerequisites:
  - User must have initiated GitHub login from `/auth/github/login`.
  - The browser must carry the stored OAuth state cookie.
- Request body:
  - None.
- Query params:
  - `code` (required on success)
  - `state` (required)
  - `error` (optional; indicates OAuth failure)
- Example request:
  ```http
  GET /auth/github/callback?code=abc123&state=xyz987
  ```
- Example response:
  - Redirect to frontend dashboard.
- Business logic:
  - Validates the callback state.
  - Exchanges the auth code for a GitHub token.
  - Fetches the user profile.
  - Creates or updates the local user record.
  - Sets the application access token cookie.

### GET /me

- Prerequisites:
  - User must be authenticated.
- Request body:
  - None.
- Example request:
  ```http
  GET /me
  ```
- Example response:
  ```json
  {
    "id": "a4d0d8c1-1d82-4ce6-8f62-1d19d3949a11",
    "github_user_id": "123456",
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "avatar_url": "https://github.com/avatar.png"
  }
  ```
- Business logic:
  - Returns the currently authenticated user profile.

### POST /auth/dev-login

- Prerequisites:
  - Only works when `settings.environment == "development"`.
  - No user session needed.
- Request body:
  ```json
  {
    "github_user_id": "123456"
  }
  ```
- Example request:
  ```http
  POST /auth/dev-login
  Content-Type: application/json
  ```
  ```json
  {
    "github_user_id": "123456"
  }
  ```
- Example response:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```
- Business logic:
  - Finds the seeded user by GitHub user ID.
  - Generates an access token.
  - Returns the token and also sets the auth cookie.

### POST /auth/logout

- Prerequisites:
  - User may be authenticated, but the endpoint handles removal of the cookie even if a session is stale.
- Request body:
  - None.
- Example request:
  ```http
  POST /auth/logout
  ```
- Example response:
  - `204 No Content`
- Business logic:
  - Removes the auth cookie for the current browser.

## 3.2 Team API

### GET /teams

- Prerequisites:
  - Authenticated user.
- Request body:
  - None.
- Example request:
  ```http
  GET /teams
  ```
- Example response:
  ```json
  [
    {
      "id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
      "name": "Platform Team",
      "role": "OWNER",
      "created_at": "2026-11-17T10:00:00Z",
      "member_count": 4,
      "project_count": 3,
      "plan_code": "FREE"
    }
  ]
  ```
- Business logic:
  - Lists all teams the current user belongs to.

### POST /teams

- Prerequisites:
  - Authenticated user.
- Request body:
  ```json
  {
    "name": "Platform Team"
  }
  ```
- Example request:
  ```http
  POST /teams
  Content-Type: application/json
  ```
  ```json
  {
    "name": "Platform Team"
  }
  ```
- Example response:
  ```json
  {
    "id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "name": "Platform Team",
    "role": "OWNER",
    "created_at": "2026-11-17T10:00:00Z",
    "member_count": 1,
    "project_count": 0,
    "plan_code": "FREE"
  }
  ```
- Business logic:
  - Validates team name.
  - Creates a team and associates the current user with it.

### GET /teams/{team_id}

- Prerequisites:
  - Authenticated user.
  - User is a member of the target team.
- Request body:
  - None.
- Example request:
  ```http
  GET /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92
  ```
- Example response:
  ```json
  {
    "id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "name": "Platform Team",
    "role": "OWNER",
    "created_at": "2026-11-17T10:00:00Z",
    "member_count": 4,
    "project_count": 3,
    "plan_code": "FREE"
  }
  ```
- Business logic:
  - Returns the team details after authorization check.

### PATCH /teams/{team_id}

- Prerequisites:
  - Authenticated user.
  - User must have permission to update the team.
- Request body:
  ```json
  {
    "name": "Platform Operations"
  }
  ```
- Example request:
  ```http
  PATCH /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92
  Content-Type: application/json
  ```
  ```json
  {
    "name": "Platform Operations"
  }
  ```
- Example response:
  ```json
  {
    "id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "name": "Platform Operations",
    "role": "OWNER",
    "created_at": "2026-11-17T10:00:00Z",
    "member_count": 4,
    "project_count": 3,
    "plan_code": "FREE"
  }
  ```
- Business logic:
  - Updates team metadata.

### GET /teams/{team_id}/members

- Prerequisites:
  - Authenticated user.
  - User is a member or authorized viewer of the team.
- Request body:
  - None.
- Example request:
  ```http
  GET /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92/members
  ```
- Example response:
  ```json
  [
    {
      "user_id": "d1b0f4b6-ff47-488d-a34d-2d9937f5ff4d",
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "avatar_url": "https://github.com/avatar.png",
      "role": "OWNER",
      "joined_at": "2026-11-17T09:30:00Z"
    }
  ]
  ```
- Business logic:
  - Returns team member roster.

## 3.3 Project API

### GET /projects

- Prerequisites:
  - Authenticated user.
- Request body:
  - None.
- Query params:
  - `status` optional, default `ACTIVE`
- Example request:
  ```http
  GET /projects?status=ACTIVE
  ```
- Example response:
  ```json
  [
    {
      "id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
      "team_name": "Platform Team",
      "name": "payments-api",
      "description": "Primary payment platform",
      "status": "ACTIVE",
      "created_at": "2026-11-17T10:10:00Z",
      "updated_at": "2026-11-17T10:25:00Z",
      "repository_count": 1,
      "deployment_count": 2
    }
  ]
  ```
- Business logic:
  - Lists projects visible to the current user and optionally filters by status.

### GET /projects/{project_id}

- Prerequisites:
  - Authenticated user.
  - User has access to the project.
- Request body:
  - None.
- Example request:
  ```http
  GET /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180
  ```
- Example response:
  ```json
  {
    "id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "team_name": "Platform Team",
    "name": "payments-api",
    "description": "Primary payment platform",
    "status": "ACTIVE",
    "created_at": "2026-11-17T10:10:00Z",
    "updated_at": "2026-11-17T10:25:00Z",
    "repository_count": 1,
    "deployment_count": 2
  }
  ```
- Business logic:
  - Returns target project details.

### PATCH /projects/{project_id}

- Prerequisites:
  - Authenticated user.
  - User must be allowed to edit the project.
- Request body:
  ```json
  {
    "name": "payments-service",
    "description": "Updated payment API service"
  }
  ```
- Example request:
  ```http
  PATCH /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180
  Content-Type: application/json
  ```
  ```json
  {
    "name": "payments-service",
    "description": "Updated payment API service"
  }
  ```
- Example response:
  ```json
  {
    "id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "team_name": "Platform Team",
    "name": "payments-service",
    "description": "Updated payment API service",
    "status": "ACTIVE",
    "created_at": "2026-11-17T10:10:00Z",
    "updated_at": "2026-11-17T10:26:00Z",
    "repository_count": 1,
    "deployment_count": 2
  }
  ```
- Business logic:
  - Updates project metadata.

### POST /projects/{project_id}/archive

- Prerequisites:
  - Authenticated user.
  - User has project edit/archive rights.
- Request body:
  - None.
- Example request:
  ```http
  POST /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/archive
  ```
- Example response:
  ```json
  {
    "id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "team_name": "Platform Team",
    "name": "payments-service",
    "description": "Updated payment API service",
    "status": "ARCHIVED",
    "created_at": "2026-11-17T10:10:00Z",
    "updated_at": "2026-11-17T10:30:00Z",
    "repository_count": 1,
    "deployment_count": 2
  }
  ```
- Business logic:
  - Marks the project as archived without deleting it.

### GET /teams/{team_id}/projects

- Prerequisites:
  - Authenticated user.
  - User can access the target team.
- Request body:
  - None.
- Query params:
  - `status` optional, default `ACTIVE`
- Example request:
  ```http
  GET /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92/projects?status=ACTIVE
  ```
- Example response:
  ```json
  [
    {
      "id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
      "team_name": "Platform Team",
      "name": "payments-service",
      "description": "Updated payment API service",
      "status": "ACTIVE",
      "created_at": "2026-11-17T10:10:00Z",
      "updated_at": "2026-11-17T10:26:00Z",
      "repository_count": 1,
      "deployment_count": 2
    }
  ]
  ```
- Business logic:
  - Lists team-scoped projects.

### POST /teams/{team_id}/projects

- Prerequisites:
  - Authenticated user.
  - User can create projects in the team.
- Request body:
  ```json
  {
    "name": "billing-service",
    "description": "Handles all invoice requests"
  }
  ```
- Example request:
  ```http
  POST /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92/projects
  Content-Type: application/json
  ```
  ```json
  {
    "name": "billing-service",
    "description": "Handles all invoice requests"
  }
  ```
- Example response:
  ```json
  {
    "id": "a1671e77-b063-42b8-8f8f-a198b542c0d8",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "team_name": "Platform Team",
    "name": "billing-service",
    "description": "Handles all invoice requests",
    "status": "ACTIVE",
    "created_at": "2026-11-17T11:00:00Z",
    "updated_at": "2026-11-17T11:00:00Z",
    "repository_count": 0,
    "deployment_count": 0
  }
  ```
- Business logic:
  - Creates a new project under the specified team.

## 3.4 Repository API

### GET /github/access

- Prerequisites:
  - Authenticated user.
  - GitHub integration context available to the backend.
- Request body:
  - None.
- Example request:
  ```http
  GET /github/access
  ```
- Example response:
  ```json
  {
    "app_configured": true,
    "app_installations": 2,
    "app_installations_usable": 2,
    "app_install_url": "https://github.com/apps/cloudpilot",
    "token_configured": true,
    "rate_limit_remaining": 5000,
    "rate_limit_limit": 5000,
    "mode_for_public_repos": "GITHUB_APP",
    "webhook_enabled": true
  }
  ```
- Business logic:
  - Returns GitHub access capability without exposing secrets.

### GET /projects/{project_id}/repositories

- Prerequisites:
  - Authenticated user.
  - Project access must be valid.
- Request body:
  - None.
- Example request:
  ```http
  GET /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/repositories
  ```
- Example response:
  ```json
  [
    {
      "id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "github_repository_id": "123456789",
      "owner": "platform-org",
      "name": "billing-service",
      "url": "https://github.com/platform-org/billing-service",
      "default_branch": "main",
      "deployment_branch": "main",
      "is_private": false,
      "access_mode": "GITHUB_APP",
      "branch_count": 8,
      "branches_truncated": false,
      "connected_at": "2026-11-17T11:05:00Z",
      "updated_at": "2026-11-17T11:05:00Z",
      "last_synced_at": "2026-11-17T11:10:00Z"
    }
  ]
  ```
- Business logic:
  - Lists repositories connected to the project.

### POST /projects/{project_id}/repositories

- Prerequisites:
  - Authenticated user.
  - User must be able to edit the project.
  - GitHub app or token access must be available.
- Request body:
  ```json
  {
    "url": "https://github.com/platform-org/billing-service"
  }
  ```
- Example request:
  ```http
  POST /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/repositories
  Content-Type: application/json
  ```
  ```json
  {
    "url": "https://github.com/platform-org/billing-service"
  }
  ```
- Example response:
  ```json
  {
    "id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "github_repository_id": "123456789",
    "owner": "platform-org",
    "name": "billing-service",
    "url": "https://github.com/platform-org/billing-service",
    "default_branch": "main",
    "deployment_branch": "main",
    "is_private": false,
    "access_mode": "GITHUB_APP",
    "branch_count": 8,
    "branches_truncated": false,
    "connected_at": "2026-11-17T11:05:00Z",
    "updated_at": "2026-11-17T11:05:00Z",
    "last_synced_at": "2026-11-17T11:10:00Z"
  }
  ```
- Business logic:
  - Connects a repository to the project by URL, then resolves the real GitHub metadata on the server.

### GET /repositories/{repo_id}

- Prerequisites:
  - Authenticated user.
  - Repository must be accessible from the user/project context.
- Request body:
  - None.
- Example request:
  ```http
  GET /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e
  ```
- Example response:
  ```json
  {
    "id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "github_repository_id": "123456789",
    "owner": "platform-org",
    "name": "billing-service",
    "url": "https://github.com/platform-org/billing-service",
    "default_branch": "main",
    "deployment_branch": "main",
    "is_private": false,
    "access_mode": "GITHUB_APP",
    "branch_count": 8,
    "branches_truncated": false,
    "connected_at": "2026-11-17T11:05:00Z",
    "updated_at": "2026-11-17T11:05:00Z",
    "last_synced_at": "2026-11-17T11:10:00Z"
  }
  ```
- Business logic:
  - Returns repository-level metadata and sync state.

### POST /repositories/{repo_id}/sync

- Prerequisites:
  - Authenticated user.
  - Repository exists and is connected.
  - GitHub access is available.
- Request body:
  - None.
- Example request:
  ```http
  POST /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/sync
  ```
- Example response:
  ```json
  {
    "id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "github_repository_id": "123456789",
    "owner": "platform-org",
    "name": "billing-service",
    "url": "https://github.com/platform-org/billing-service",
    "default_branch": "main",
    "deployment_branch": "main",
    "is_private": false,
    "access_mode": "GITHUB_APP",
    "branch_count": 8,
    "branches_truncated": false,
    "connected_at": "2026-11-17T11:05:00Z",
    "updated_at": "2026-11-17T11:11:00Z",
    "last_synced_at": "2026-11-17T11:11:00Z"
  }
  ```
- Business logic:
  - Refreshes repository metadata from GitHub and updates the local record.

### GET /repositories/{repo_id}/branches

- Prerequisites:
  - Authenticated user.
  - Repository is accessible.
- Request body:
  - None.
- Example request:
  ```http
  GET /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/branches
  ```
- Example response:
  ```json
  [
    {
      "id": "f86f9de4-6cf4-4c1e-87f5-9998d3d0f402",
      "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "name": "main",
      "is_default": true,
      "is_deployment_branch": true
    },
    {
      "id": "b0d480e4-3ca8-4566-88eb-7f51b7d31395",
      "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "name": "feature/add-auth",
      "is_default": false,
      "is_deployment_branch": false
    }
  ]
  ```
- Business logic:
  - Lists all tracked branches and flags the default and deployment selection.

### PUT /repositories/{repo_id}/deployment-branch

- Prerequisites:
  - Authenticated user.
  - Repository is connected and accessible.
- Request body:
  ```json
  {
    "branch_name": "develop"
  }
  ```
- Example request:
  ```http
  PUT /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/deployment-branch
  Content-Type: application/json
  ```
  ```json
  {
    "branch_name": "develop"
  }
  ```
- Example response:
  ```json
  {
    "id": "b0d480e4-3ca8-4566-88eb-7f51b7d31395",
    "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "name": "develop",
    "is_default": false,
    "is_deployment_branch": true
  }
  ```
- Business logic:
  - Sets the branch used as the deployment branch.

### GET /repositories/{repo_id}/commits

- Prerequisites:
  - Authenticated user.
  - Repository access is valid.
- Request body:
  - None.
- Query params:
  - `branch` optional
  - `refresh` optional boolean, default false
  - `limit` optional 1-100, default 20
  - `offset` optional 0-500, default 0
- Example request:
  ```http
  GET /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/commits?branch=main&limit=10&offset=0
  ```
- Example response:
  ```json
  [
    {
      "id": "04f80248-f6b2-43de-8d0e-2c44f5b8ef4d",
      "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "branch_id": "f86f9de4-6cf4-4c1e-87f5-9998d3d0f402",
      "sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2",
      "message": "feat: add customer billing endpoint",
      "author_name": "Alice Johnson",
      "committed_at": "2026-11-17T10:59:00Z"
    }
  ]
  ```
- Business logic:
  - Returns commit history for the repository and branch, optionally refreshing from GitHub.

## 3.5 Analysis API

### POST /repositories/{repo_id}/analyses

- Prerequisites:
  - Authenticated user.
  - Repository exists and belongs to the allowed project.
  - GitHub access may be needed to inspect repo contents.
- Request body:
  ```json
  {
    "branch": "main",
    "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2"
  }
  ```
  or empty object for defaults.
- Headers:
  - `Idempotency-Key` optional
- Example request:
  ```http
  POST /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/analyses
  Idempotency-Key: 8d54f40b-a64a-4d01-b25e-9dc1b7a5d7eb
  Content-Type: application/json
  ```
  ```json
  {
    "branch": "main",
    "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2"
  }
  ```
- Example response:
  ```json
  {
    "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "commit_id": "f7c777d4-31f4-4cd5-a7bc-6cfcc74c2cb8",
    "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2",
    "branch_name": "main",
    "status": "QUEUED",
    "terminal": false,
    "created_at": "2026-11-17T11:25:00Z",
    "started_at": null,
    "completed_at": null,
    "duration_ms": null,
    "requested_by": "d1b0f4b6-ff47-488d-a34d-2d9937f5ff4d",
    "attempts": 1,
    "cancel_requested": false,
    "parent_analysis_id": null,
    "user_answers": {},
    "error_code": null,
    "error_message": null,
    "warnings": [],
    "services_count": 0,
    "report": null
  }
  ```
- Business logic:
  - Queues an async repository analysis.
  - Poll the returned job endpoint until status becomes terminal.

### GET /analyses/{analysis_id}

- Prerequisites:
  - Authenticated user.
  - User can access the analysis.
- Request body:
  - None.
- Example request:
  ```http
  GET /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f
  ```
- Example response:
  ```json
  {
    "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "commit_id": "f7c777d4-31f4-4cd5-a7bc-6cfcc74c2cb8",
    "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2",
    "branch_name": "main",
    "status": "SUCCESS",
    "terminal": true,
    "created_at": "2026-11-17T11:25:00Z",
    "started_at": "2026-11-17T11:25:10Z",
    "completed_at": "2026-11-17T11:28:40Z",
    "duration_ms": 210000,
    "requested_by": "d1b0f4b6-ff47-488d-a34d-2d9937f5ff4d",
    "attempts": 1,
    "cancel_requested": false,
    "parent_analysis_id": null,
    "user_answers": {},
    "error_code": null,
    "error_message": null,
    "warnings": [],
    "services_count": 3,
    "report": {
      "summary": "Repository analyzed successfully"
    }
  }
  ```
- Business logic:
  - Returns the current state of the analysis task.

### GET /analyses/{analysis_id}/activity

- Prerequisites:
  - Authenticated user.
  - Allowed to view the analysis job.
- Request body:
  - None.
- Example request:
  ```http
  GET /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f/activity
  ```
- Example response:
  ```json
  {
    "analysis_id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "status": "RUNNING",
    "terminal": false,
    "attempts": 1,
    "cancel_requested": false,
    "heartbeat_at": "2026-11-17T11:27:00Z",
    "runs": [
      {
        "id": "97d9a9f5-9ab7-4cb9-bd90-d34bf7d5dc66",
        "agent_type": "repo_inspector",
        "status": "RUNNING",
        "model": "gpt-4o-mini",
        "usage": {"input_tokens": 1200, "output_tokens": 450},
        "started_at": "2026-11-17T11:27:00Z",
        "completed_at": null,
        "duration_ms": null,
        "input": {"repo": "billing-service"},
        "output": null,
        "error_code": null,
        "error_message": null,
        "tasks": []
      }
    ]
  }
  ```
- Business logic:
  - Shows live execution state used by the activity UI.

### GET /analyses/{analysis_id}/services

- Prerequisites:
  - Authenticated user.
  - Analysis exists and is accessible.
- Request body:
  - None.
- Example request:
  ```http
  GET /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f/services
  ```
- Example response:
  ```json
  [
    {"name": "api", "type": "web_service"},
    {"name": "worker", "type": "job_processor"},
    {"name": "postgres", "type": "database"}
  ]
  ```
- Business logic:
  - Returns discovered service inventory used for architecture and deployment planning.

### POST /analyses/{analysis_id}/cancel

- Prerequisites:
  - Authenticated user.
  - User is allowed to cancel the job.
- Request body:
  - None.
- Example request:
  ```http
  POST /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f/cancel
  ```
- Example response:
  ```json
  {
    "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "status": "CANCEL_REQUESTED",
    "terminal": false,
    "cancel_requested": true
  }
  ```
- Business logic:
  - Marks the analysis for cancellation without destroying the record immediately.

### POST /analyses/{analysis_id}/answers

- Prerequisites:
  - Authenticated user.
  - Analysis is currently in a blocked state and requires answers.
- Request body:
  ```json
  {
    "answers": {
      "database_choice": "PostgreSQL",
      "deployment_target": "AWS"
    }
  }
  ```
- Example request:
  ```http
  POST /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f/answers
  Content-Type: application/json
  ```
  ```json
  {
    "answers": {
      "database_choice": "PostgreSQL",
      "deployment_target": "AWS"
    }
  }
  ```
- Example response:
  ```json
  {
    "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "status": "QUEUED",
    "terminal": false,
    "user_answers": {
      "database_choice": "PostgreSQL",
      "deployment_target": "AWS"
    }
  }
  ```
- Business logic:
  - Resubmits the analysis with collected user answers so the worker can continue.

### GET /repositories/{repo_id}/analyses

- Prerequisites:
  - Authenticated user.
  - Repository is connected and accessible.
- Request body:
  - None.
- Query params:
  - `limit` optional, 1-100
  - `offset` optional, >=0
- Example request:
  ```http
  GET /repositories/7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e/analyses?limit=10&offset=0
  ```
- Example response:
  ```json
  [
    {
      "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
      "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2",
      "branch_name": "main",
      "status": "SUCCESS",
      "terminal": true,
      "created_at": "2026-11-17T11:25:00Z"
    }
  ]
  ```
- Business logic:
  - Lists repository analysis history.

### GET /projects/{project_id}/analyses

- Prerequisites:
  - Authenticated user.
  - User has access to the project.
- Request body:
  - None.
- Query params:
  - `limit` optional, 1-100
  - `offset` optional, >=0
- Example request:
  ```http
  GET /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/analyses?limit=10&offset=0
  ```
- Example response:
  ```json
  [
    {
      "id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
      "repository_id": "7d38ec6a-331d-4e3a-aa5a-c0cf14d8a59e",
      "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "commit_sha": "8c2b9e7a4d1e3ae7b3c3b8aebd0a1f4a5f2d9d2",
      "branch_name": "main",
      "status": "SUCCESS",
      "terminal": true,
      "created_at": "2026-11-17T11:25:00Z"
    }
  ]
  ```
- Business logic:
  - Returns analyses at project scope.

## 3.6 Architecture API

### POST /analyses/{analysis_id}/architectures

- Prerequisites:
  - Authenticated user.
  - Analysis must exist and belong to accessible project.
- Request body:
  ```json
  {
    "preferred_provider": "aws",
    "region": "us-east-1"
  }
  ```
  This is optional; the service may use defaults if omitted.
- Example request:
  ```http
  POST /analyses/c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f/architectures
  Content-Type: application/json
  ```
  ```json
  {
    "preferred_provider": "aws",
    "region": "us-east-1"
  }
  ```
- Example response:
  ```json
  {
    "id": "0d4c86dc-afb1-4a8d-9fca-63d180294476",
    "analysis_id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "version_number": 1,
    "status": "READY"
  }
  ```
- Business logic:
  - Takes analysis results and produces a versioned architecture proposal.

### GET /projects/{project_id}/architectures

- Prerequisites:
  - Authenticated user.
  - Project access permission.
- Request body:
  - None.
- Example request:
  ```http
  GET /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/architectures
  ```
- Example response:
  ```json
  [
    {
      "id": "0d4c86dc-afb1-4a8d-9fca-63d180294476",
      "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "version_number": 1,
      "status": "READY"
    }
  ]
  ```
- Business logic:
  - Lists architecture proposals for the project.

### GET /architectures/{architecture_id}/versions/{version_number}

- Prerequisites:
  - Authenticated user.
  - Architecture version is accessible.
- Request body:
  - None.
- Example request:
  ```http
  GET /architectures/0d4c86dc-afb1-4a8d-9fca-63d180294476/versions/1
  ```
- Example response:
  ```json
  {
    "id": "0d4c86dc-afb1-4a8d-9fca-63d180294476",
    "analysis_id": "c4a3f416-3a90-4b3c-bb28-0b2c47bfc05f",
    "version_number": 1,
    "status": "READY",
    "content": {
      "services": ["api", "worker", "postgres"],
      "cloud": "aws"
    }
  }
  ```
- Business logic:
  - Returns a specific version of a generated architecture proposal.

## 3.7 Deployment API

### POST /teams/{team_id}/aws-accounts

- Prerequisites:
  - Authenticated user.
  - Team access and valid AWS account onboarding context.
- Request body:
  ```json
  {
    "account_id": "111111111111",
    "role_arn": "arn:aws:iam::111111111111:role/CloudPilotRole",
    "external_id": "cloudpilot-tenant-01"
  }
  ```
- Example request:
  ```http
  POST /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92/aws-accounts
  Content-Type: application/json
  ```
  ```json
  {
    "account_id": "111111111111",
    "role_arn": "arn:aws:iam::111111111111:role/CloudPilotRole",
    "external_id": "cloudpilot-tenant-01"
  }
  ```
- Example response:
  ```json
  {
    "id": "d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "account_id": "111111111111",
    "status": "CONNECTED"
  }
  ```
- Business logic:
  - Connects an AWS account to a team so deployment workflows can use that account.

### GET /teams/{team_id}/aws-accounts

- Prerequisites:
  - Authenticated user.
  - Team access permission.
- Request body:
  - None.
- Example request:
  ```http
  GET /teams/f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92/aws-accounts
  ```
- Example response:
  ```json
  [
    {
      "id": "d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed",
      "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
      "account_id": "111111111111",
      "status": "CONNECTED"
    }
  ]
  ```
- Business logic:
  - Lists AWS accounts connected to the team.

### GET /aws-accounts/{account_id}/onboarding

- Prerequisites:
  - Authenticated user.
  - Account must be connected and visible to the user.
- Request body:
  - None.
- Example request:
  ```http
  GET /aws-accounts/d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed/onboarding
  ```
- Example response:
  ```json
  {
    "account_id": "111111111111",
    "cloudformation_template_url": "https://example.com/template.yml",
    "instructions": "Create the CloudFormation stack from the template and confirm the IAM trust relationship."
  }
  ```
- Business logic:
  - Produces AWS onboarding details and template instructions.

### POST /aws-accounts/{account_id}/verify

- Prerequisites:
  - Authenticated user.
  - AWS account is connected.
  - Platform has access to perform STS AssumeRole checks.
- Request body:
  - None.
- Example request:
  ```http
  POST /aws-accounts/d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed/verify
  ```
- Example response:
  ```json
  {
    "id": "d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed",
    "team_id": "f0cb21f2-2d8f-4c0f-bd4d-0ef4e9609f92",
    "account_id": "111111111111",
    "status": "VERIFIED"
  }
  ```
- Business logic:
  - Verifies cross-account AWS access using the configured trust relationship.

### GET /network/egress-ip

- Prerequisites:
  - Authenticated user.
- Request body:
  - None.
- Example request:
  ```http
  GET /network/egress-ip
  ```
- Example response:
  ```json
  {
    "ip": "54.12.34.56"
  }
  ```
- Business logic:
  - Returns the public egress IP used for outbound deployment traffic.

### POST /projects/{project_id}/deployments

- Prerequisites:
  - Authenticated user.
  - Project is accessible.
  - A connected AWS account and repository context should exist.
- Request body:
  ```json
  {
    "name": "prod-deploy-v1",
    "architecture_id": "0d4c86dc-afb1-4a8d-9fca-63d180294476",
    "aws_account_id": "d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed"
  }
  ```
- Example request:
  ```http
  POST /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/deployments
  Content-Type: application/json
  ```
  ```json
  {
    "name": "prod-deploy-v1",
    "architecture_id": "0d4c86dc-afb1-4a8d-9fca-63d180294476",
    "aws_account_id": "d8d741d8-42e8-4d96-b5d7-bcf9ddee91ed"
  }
  ```
- Example response:
  ```json
  {
    "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "status": "PLANNED"
  }
  ```
- Business logic:
  - Creates a deployment plan but does not apply changes until approval and execution.

### GET /projects/{project_id}/deployments

- Prerequisites:
  - Authenticated user.
  - Project access.
- Request body:
  - None.
- Example request:
  ```http
  GET /projects/7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180/deployments
  ```
- Example response:
  ```json
  [
    {
      "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
      "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
      "status": "PLANNED"
    }
  ]
  ```
- Business logic:
  - Lists deployment history for the project.

### GET /deployments/{deployment_id}

- Prerequisites:
  - Authenticated user.
  - User can access the deployment.
- Request body:
  - None.
- Example request:
  ```http
  GET /deployments/8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb
  ```
- Example response:
  ```json
  {
    "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "status": "PLANNED",
    "created_at": "2026-11-17T11:35:00Z"
  }
  ```
- Business logic:
  - Returns deployment record and status.

### GET /deployments/{deployment_id}/audit

- Prerequisites:
  - Authenticated user.
  - User can access the deployment record.
- Request body:
  - None.
- Example request:
  ```http
  GET /deployments/8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb/audit
  ```
- Example response:
  ```json
  [
    {
      "id": "cd20dca2-f9d8-42bf-b8b5-fe40de5287fd",
      "deployment_id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
      "event": "PLAN_CREATED",
      "actor_id": "d1b0f4b6-ff47-488d-a34d-2d9937f5ff4d",
      "created_at": "2026-11-17T11:35:05Z"
    }
  ]
  ```
- Business logic:
  - Returns historical audit events connected to the deployment.

### POST /deployments/{deployment_id}/approve

- Prerequisites:
  - Authenticated user.
  - User has approval rights.
  - The reviewed plan hash must match the actual plan.
- Request body:
  ```json
  {
    "approved": true,
    "plan_hash": "7d8a575e95a8f3019b6b6b0d7b42a8fe6a84bee4"
  }
  ```
- Example request:
  ```http
  POST /deployments/8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb/approve
  Content-Type: application/json
  ```
  ```json
  {
    "approved": true,
    "plan_hash": "7d8a575e95a8f3019b6b6b0d7b42a8fe6a84bee4"
  }
  ```
- Example response:
  ```json
  {
    "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
    "decision": "APPROVED",
    "approved_by": "d1b0f4b6-ff47-488d-a34d-2d9937f5ff4d"
  }
  ```
- Business logic:
  - Records approval or rejection against the deployment plan after verifying the reviewed hash.

### POST /deployments/{deployment_id}/apply

- Prerequisites:
  - Authenticated user.
  - Deployment must be approved.
- Request body:
  - None.
- Example request:
  ```http
  POST /deployments/8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb/apply
  ```
- Example response:
  ```json
  {
    "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "status": "APPLYING"
  }
  ```
- Business logic:
  - Starts the actual infrastructure execution flow for an approved deployment.

### POST /deployments/{deployment_id}/destroy

- Prerequisites:
  - Authenticated user.
  - Access to the deployment and valid teardown context.
- Request body:
  ```json
  {
    "confirm": true,
    "reason": "Retiring old environment"
  }
  ```
- Example request:
  ```http
  POST /deployments/8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb/destroy
  Content-Type: application/json
  ```
  ```json
  {
    "confirm": true,
    "reason": "Retiring old environment"
  }
  ```
- Example response:
  ```json
  {
    "id": "8c3e0c24-cd8d-4c96-9eec-c88c4be6d5fb",
    "project_id": "7ce3d98e-27bf-4f29-b3f1-f6f7dfd47180",
    "status": "DESTROYING"
  }
  ```
- Business logic:
  - Executes the teardown workflow for a deployment.

## 3.8 Webhook API

### POST /webhooks/github

- Prerequisites:
  - GitHub must be configured with the webhook secret.
  - Request must include valid `X-Hub-Signature-256` header.
  - Payload must not exceed the size limit.
- Request body:
  - Raw JSON payload from GitHub, usually a push event.
- Headers:
  - `X-GitHub-Event: push` or `ping`
  - `X-Hub-Signature-256: sha256=<signature>`
- Example request:
  ```http
  POST /webhooks/github
  X-GitHub-Event: push
  X-Hub-Signature-256: sha256=abcdef1234567890
  Content-Type: application/json
  ```
  ```json
  {
    "ref": "refs/heads/main",
    "repository": {
      "full_name": "platform-org/billing-service",
      "clone_url": "https://github.com/platform-org/billing-service.git"
    },
    "pusher": {
      "name": "alice"
    }
  }
  ```
- Example response:
  - `202 Accepted` for valid push payloads
  - `204 No Content` for ping events
- Business logic:
  - Validates the HMAC signature.
  - Ignores unsupported events.
  - Parses JSON and forwards push payloads to the webhook service.

## 3.9 LLM API

### GET /llm/providers

- Prerequisites:
  - Authenticated user.
- Request body:
  - None.
- Query params:
  - `refresh` optional boolean
- Example request:
  ```http
  GET /llm/providers?refresh=false
  ```
- Example response:
  ```json
  [
    {
      "name": "openai",
      "real": true,
      "available": true,
      "selected_model": "gpt-4o-mini",
      "mock_only": false
    }
  ]
  ```
- Business logic:
  - Reports provider availability and configured model status without exposing secrets.

## 3.10 Health API

### GET /health/db

- Prerequisites:
  - Backend can reach the configured database.
- Request body:
  - None.
- Example request:
  ```http
  GET /health/db
  ```
- Example response:
  ```json
  {
    "database": "ok"
  }
  ```
- Business logic:
  - Executes a lightweight DB health check to confirm the DB connection is healthy.

## 4. End-to-End Flow

1. User logs in via GitHub or development login.
2. User creates or joins a team.
3. User creates a project inside the team.
4. User connects a GitHub repository to the project.
5. User triggers an AI analysis of the repo.
6. User creates an architecture proposal from the analysis.
7. User creates a deployment plan using the architecture and AWS account.
8. Deployment requires approval before apply.
9. Approved deployment executes infrastructure changes.
10. Deployment events and audits are tracked for review and operations.

## 5. Notes for Integrators

- All authenticated routes require a valid user session or token.
- Endpoint bodies must match the JSON contract exactly.
- For async endpoints, always check the returned job status before assuming completion.
- For deployment actions, plan approval is a required business gate before apply.
- GitHub webhook calls are not cookie-authenticated; they rely on cryptographic signature validation.

This document is intended as a practical guide for frontend developers, API consumers, and platform engineers working with the CloudPilot backend.
