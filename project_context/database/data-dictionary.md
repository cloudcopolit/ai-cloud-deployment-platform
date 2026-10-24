# Data Dictionary

> 27 tables, generated from the same spec as `schema-full.sql`. Legend: ✅ exists in code · 📋 in ERD only · 💡 proposed here.
> **New** = column/constraint that is *not* in the original `.drawio` (proposal, see `04` §7). Types follow the draft DDL (PostgreSQL 16).

| # | Table | Domain | Status | Purpose |
|---|---|---|:-:|---|
| 1 | [`users`](#users) | Identity | ✅ | A person who signed in with GitHub. |
| 2 | [`teams`](#teams) | Identity | ✅ | Tenant / workspace. Owns projects, AWS accounts, subscription. |
| 3 | [`team_members`](#team_members) | Identity | ✅ | Junction users↔teams with a role. |
| 4 | [`plans`](#plans) | Subscription | ✅ | Catalog of plans (FREE, STANDARD). Missing from the ERD (D1). Column list is inferred from the README/seed, verify against the model. |
| 5 | [`subscriptions`](#subscriptions) | Subscription | ✅ | A team's plan. Missing from the ERD (D1). Inferred columns, verify against the model. |
| 6 | [`projects`](#projects) | Project | ✅ | A deployable application. Archived, never deleted. |
| 7 | [`repositories`](#repositories) | Source Control | ✅ | GitHub repo connected to a project. Metadata only, never source code. |
| 8 | [`branches`](#branches) | Source Control | ✅ | Branches of a repo. Exactly one deployment branch per repo. |
| 9 | [`commits`](#commits) | Source Control | ✅ | Immutable commit records of the deployment branch. |
| 10 | [`repository_analyses`](#repository_analyses) | Analysis | 📋 | One run of the Analysis Agent on a repo at a commit = the 'analysis job'. |
| 11 | [`services`](#services) | Analysis | 📋 | Normalized DetectedService rows of one analysis. |
| 12 | [`architectures`](#architectures) | Architecture | 📋 | Named design container; versions hold the content. |
| 13 | [`architecture_versions`](#architecture_versions) | Architecture | 📋 | Immutable numbered snapshot of the AWS design (ArchitecturePlan). |
| 14 | [`cost_estimates`](#cost_estimates) | Cost | 📋 | Estimated monthly cost of one architecture version. |
| 15 | [`aws_accounts`](#aws_accounts) | AWS | 📋 | Customer AWS account reached through IAM role + External ID. Never stores keys. |
| 16 | [`deployments`](#deployments) | Deployment | 📋 | One deployment attempt. Pins the exact commit + architecture version + AWS account. |
| 17 | [`deployment_steps`](#deployment_steps) | Deployment | 📋 | Ordered stage of a deployment, so the failing step is identifiable. |
| 18 | [`infrastructure_resources`](#infrastructure_resources) | Deployment | 📋 | AWS resources created by a deployment. |
| 19 | [`monitoring_configs`](#monitoring_configs) | Monitoring | 📋 | Monitoring settings of a deployment. |
| 20 | [`alerts`](#alerts) | Monitoring | 📋 | A fired alert (metric crossed a threshold). |
| 21 | [`cost_records`](#cost_records) | Cost | 📋 | Actual cost of a period, imported from AWS, compared with estimates. |
| 22 | [`incidents`](#incidents) | Incident | 📋 | A detected problem on a project/deployment. |
| 23 | [`agent_runs`](#agent_runs) | AI Agents | 📋 | One execution of an AI agent. Trace for analysis, architecture, diagnosis. |
| 24 | [`agent_tasks`](#agent_tasks) | AI Agents | 📋 | Ordered step inside an agent run (fetch, detect, validate ...). |
| 25 | [`healing_actions`](#healing_actions) | Incident | 📋 | Corrective action proposed for an incident. |
| 26 | [`approvals`](#approvals) | Incident | 📋 | Human decision gate. Generalized to deployments (ADR-011). |
| 27 | [`audit_logs`](#audit_logs) | Audit | 💡 | Append-only trail of sensitive actions (README 'Audit' domain, absent in ERD). |

## users

✅ **Identity** · A person who signed in with GitHub.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `github_user_id` | varchar(64) | no |  | UNIQUE | GitHub numeric id as string |
| `name` | varchar(255) | yes |  |  |  |
| `email` | varchar(320) | yes |  | UNIQUE | may stay NULL if hidden or colliding |
| `avatar_url` | text | yes |  |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

## teams

✅ **Identity** · Tenant / workspace. Owns projects, AWS accounts, subscription.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `name` | varchar(255) | no |  |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

## team_members

✅ **Identity** · Junction users↔teams with a role.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `team_id` | uuid | no |  | PK; FK → teams.id |  |
| `user_id` | uuid | no |  | PK; FK → users.id |  |
| `role` | varchar(16) | no |  | CHECK: OWNER, ADMIN, MEMBER | Python-side default MEMBER |
| `joined_at` | timestamptz | no | `now()` |  |  |

## plans

✅ **Subscription** · Catalog of plans (FREE, STANDARD). Missing from the ERD (D1). Column list is inferred from the README/seed, verify against the model.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `code` | varchar(32) | no |  | UNIQUE | FREE / STANDARD · inferred |
| `name` | varchar(100) | no |  |  | inferred |
| `price_monthly` | numeric(10,2) | no | `0` |  | inferred |
| `limits` | jsonb | no |  |  | {max_projects,max_team_members,max_deployments_per_month} · inferred |
| `created_at` | timestamptz | no | `now()` |  | inferred |

## subscriptions

✅ **Subscription** · A team's plan. Missing from the ERD (D1). Inferred columns, verify against the model.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `team_id` | uuid | no |  | FK → teams.id | inferred |
| `plan_id` | uuid | no |  | FK → plans.id | inferred |
| `status` | varchar(16) | no |  | CHECK: ACTIVE, TRIALING, PAST_DUE, CANCELED | inferred |
| `started_at` | timestamptz | no | `now()` |  | inferred |
| `ended_at` | timestamptz | yes |  |  | inferred |
| `created_at` | timestamptz | no | `now()` |  | inferred |

Extra constraints / indexes:

- `CREATE UNIQUE INDEX uq_subscriptions_one_active_per_team ON subscriptions (team_id) WHERE status IN ('ACTIVE','TRIALING');`

## projects

✅ **Project** · A deployable application. Archived, never deleted.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `team_id` | uuid | no |  | FK → teams.id |  |
| `name` | varchar(255) | no |  |  |  |
| `description` | text | yes |  |  |  |
| `status` | varchar(16) | no | `'ACTIVE'` | CHECK: ACTIVE, ARCHIVED |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

## repositories

✅ **Source Control** · GitHub repo connected to a project. Metadata only, never source code.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `github_repository_id` | varchar(64) | no |  |  | UNIQUE per project in code; ERD says global (D3) |
| `owner` | varchar(255) | no |  |  |  |
| `name` | varchar(255) | no |  |  |  |
| `url` | text | no |  |  |  |
| `default_branch` | varchar(255) | no |  |  |  |
| `connected_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `ALTER TABLE repositories ADD CONSTRAINT uq_repositories_project_id_github_repository_id UNIQUE (project_id, github_repository_id);`

## branches

✅ **Source Control** · Branches of a repo. Exactly one deployment branch per repo.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `repository_id` | uuid | no |  | FK → repositories.id |  |
| `name` | varchar(255) | no |  |  |  |
| `is_default` | boolean | no | `false` |  |  |
| `is_deployment_branch` | boolean | no | `false` |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `ALTER TABLE branches ADD CONSTRAINT uq_branches_repository_id_name UNIQUE (repository_id, name);`
- `CREATE UNIQUE INDEX uq_branches_one_deployment_branch ON branches (repository_id) WHERE is_deployment_branch;`

## commits

✅ **Source Control** · Immutable commit records of the deployment branch.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `repository_id` | uuid | no |  | FK → repositories.id |  |
| `branch_id` | uuid | no |  | FK → branches.id |  |
| `sha` | varchar(40) | no |  |  | unique per repository, not global (D4) |
| `message` | text | yes |  |  |  |
| `author_name` | varchar(255) | yes |  |  |  |
| `author_email` | varchar(320) | yes |  |  |  |
| `committed_at` | timestamptz | no |  |  |  |
| `detected_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `ALTER TABLE commits ADD CONSTRAINT uq_commits_repository_id_sha UNIQUE (repository_id, sha);`
- `CREATE INDEX ix_commits_repository_id_committed_at ON commits (repository_id, committed_at DESC);`

## repository_analyses

📋 **Analysis** · One run of the Analysis Agent on a repo at a commit = the 'analysis job'.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `repository_id` | uuid | no |  | FK → repositories.id |  |
| `commit_id` | uuid | no |  | FK → commits.id |  |
| `status` | varchar(16) | no | `'QUEUED'` | CHECK: QUEUED, RUNNING, SUCCESS, BLOCKED, FAILED, TIMED_OUT, CANCELLED | 💡 BLOCKED, TIMED_OUT, CANCELLED added (ADR-007) |
| `created_at` | timestamptz | no | `now()` |  | **New** · 💡 stable ordering while QUEUED (P3) |
| `started_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `requested_by` | uuid | yes |  | FK → users.id | **New** · 💡 who triggered it (P4) |
| `report_schema_version` | varchar(8) | yes |  |  | **New** · 💡 contract version (P4) |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  | safe to show to users |
| `analysis_data` | jsonb | yes |  |  | validated AnalysisReport with evidence metadata only; no source excerpts |

Extra constraints / indexes:

- `CREATE INDEX ix_repository_analyses_status_created_at ON repository_analyses (status, created_at);`

## services

📋 **Analysis** · Normalized DetectedService rows of one analysis.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `analysis_id` | uuid | no |  | FK → repository_analyses.id |  |
| `name` | varchar(255) | no |  |  |  |
| `service_type` | varchar(32) | no |  |  | api / web / worker / cron / database ... |
| `language` | varchar(64) | yes |  |  |  |
| `framework` | varchar(64) | yes |  |  |  |
| `path` | varchar(1024) | no | `'.'` |  |  |
| `port` | integer | yes |  | CHECK 1..65535 |  |
| `metadata` | jsonb | no | `'{}'::jsonb` |  | has_dockerfile, health_endpoint, confidence ... |
| `created_at` | timestamptz | no | `now()` |  |  |

## architectures

📋 **Architecture** · Named design container; versions hold the content.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `name` | varchar(255) | no |  |  |  |
| `status` | varchar(16) | no | `'ACTIVE'` | CHECK: ACTIVE, ARCHIVED | 💡 values |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

## architecture_versions

📋 **Architecture** · Immutable numbered snapshot of the AWS design (ArchitecturePlan).

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `architecture_id` | uuid | no |  | FK → architectures.id |  |
| `version_number` | integer | no |  | CHECK > 0 |  |
| `source_analysis_id` | uuid | yes |  | FK → repository_analyses.id | NULL when the user authored the version by hand |
| `status` | varchar(16) | no | `'DRAFT'` | CHECK: DRAFT, VALIDATED, INVALID, APPROVED, SUPERSEDED | 💡 values (07 §4) |
| `architecture_data` | jsonb | no |  |  | validated ArchitecturePlan; immutable once APPROVED |
| `created_by` | uuid | yes |  | FK → users.id | NULL = created by the Architecture Agent |
| `created_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `ALTER TABLE architecture_versions ADD CONSTRAINT uq_architecture_versions_architecture_id_version_number UNIQUE (architecture_id, version_number);`

## cost_estimates

📋 **Cost** · Estimated monthly cost of one architecture version.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `architecture_version_id` | uuid | no |  | FK → architecture_versions.id |  |
| `estimated_monthly_cost` | numeric(12,2) | no |  |  |  |
| `currency` | char(3) | no | `'USD'` |  |  |
| `breakdown` | jsonb | no |  |  | per-component lines + pricing_as_of |
| `calculated_at` | timestamptz | no | `now()` |  |  |

## aws_accounts

📋 **AWS** · Customer AWS account reached through IAM role + External ID. Never stores keys.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `team_id` | uuid | no |  | FK → teams.id |  |
| `aws_account_id` | varchar(12) | no |  |  | 12-digit account id |
| `role_arn` | text | yes |  |  | deploy role (write); NULL until verified |
| `readonly_role_arn` | text | yes |  |  | **New** · 💡 planning-time read-only role (P12 / ADR-010) |
| `external_id` | varchar(64) | no |  |  | **New** · 💡 random per account, used in AssumeRole (P2) |
| `default_region` | varchar(32) | no |  |  |  |
| `status` | varchar(24) | no | `'PENDING_VERIFICATION'` | CHECK: PENDING_VERIFICATION, ACTIVE, VERIFICATION_FAILED, DISCONNECTED | 💡 values |
| `connected_at` | timestamptz | no | `now()` |  |  |
| `last_verified_at` | timestamptz | yes |  |  |  |

Extra constraints / indexes:

- `CREATE UNIQUE INDEX uq_aws_accounts_team_id_aws_account_id ON aws_accounts (team_id, aws_account_id) WHERE status <> 'DISCONNECTED';` — disconnected rows do not block reconnecting the same account.
- `ALTER TABLE aws_accounts ADD CONSTRAINT uq_aws_accounts_external_id UNIQUE (external_id);`

## deployments

📋 **Deployment** · One deployment attempt. Pins the exact commit + architecture version + AWS account.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `repository_id` | uuid | no |  | FK → repositories.id |  |
| `commit_id` | uuid | no |  | FK → commits.id |  |
| `architecture_version_id` | uuid | no |  | FK → architecture_versions.id |  |
| `aws_account_id` | uuid | no |  | FK → aws_accounts.id |  |
| `status` | varchar(16) | no | `'QUEUED'` | CHECK: QUEUED, RUNNING, SUCCESS, FAILED, CANCELLED |  |
| `trigger_type` | varchar(16) | no | `'MANUAL'` | CHECK: MANUAL, AUTO, RETRY, HEALING |  |
| `created_at` | timestamptz | no | `now()` |  | **New** · 💡 (P3) |
| `started_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  |  |
| `created_by` | uuid | yes |  | FK → users.id | NULL for AUTO/HEALING |

Extra constraints / indexes:

- `CREATE UNIQUE INDEX uq_deployments_one_active_per_project ON deployments (project_id) WHERE status IN ('QUEUED','RUNNING');`
- `CREATE INDEX ix_deployments_project_id_created_at ON deployments (project_id, created_at DESC);`

## deployment_steps

📋 **Deployment** · Ordered stage of a deployment, so the failing step is identifiable.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `deployment_id` | uuid | no |  | FK → deployments.id |  |
| `step_type` | varchar(32) | no |  |  | see 07 §6 |
| `step_order` | integer | no |  | CHECK > 0 |  |
| `status` | varchar(16) | no | `'QUEUED'` | CHECK: QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED |  |
| `created_at` | timestamptz | no | `now()` |  | **New** · 💡 (P3) |
| `started_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  |  |
| `input_data` | jsonb | yes |  |  |  |
| `output_data` | jsonb | yes |  |  | plan summary, never Terraform state |

Extra constraints / indexes:

- `ALTER TABLE deployment_steps ADD CONSTRAINT uq_deployment_steps_deployment_id_step_order UNIQUE (deployment_id, step_order);`

## infrastructure_resources

📋 **Deployment** · AWS resources created by a deployment.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `deployment_id` | uuid | no |  | FK → deployments.id |  |
| `resource_type` | varchar(64) | no |  |  | e.g. aws_ecs_service |
| `resource_name` | varchar(255) | no |  |  |  |
| `aws_resource_id` | varchar(255) | yes |  |  |  |
| `aws_arn` | text | yes |  |  |  |
| `region` | varchar(32) | no |  |  |  |
| `status` | varchar(16) | no | `'ACTIVE'` | CHECK: CREATING, ACTIVE, FAILED, DESTROYED | 💡 values |
| `metadata` | jsonb | no | `'{}'::jsonb` |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

## monitoring_configs

📋 **Monitoring** · Monitoring settings of a deployment.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `deployment_id` | uuid | no |  | FK → deployments.id |  |
| `enabled` | boolean | no | `true` |  |  |
| `configuration` | jsonb | no |  |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |
| `updated_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `ALTER TABLE monitoring_configs ADD CONSTRAINT uq_monitoring_configs_deployment_id UNIQUE (deployment_id);`

## alerts

📋 **Monitoring** · A fired alert (metric crossed a threshold).

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `deployment_id` | uuid | no |  | FK → deployments.id |  |
| `severity` | varchar(16) | no |  | CHECK: LOW, MEDIUM, HIGH, CRITICAL | 💡 values |
| `source` | varchar(32) | no |  |  | PROMETHEUS / CLOUDWATCH |
| `metric_name` | varchar(255) | no |  |  |  |
| `threshold` | numeric | yes |  |  |  |
| `actual_value` | numeric | yes |  |  |  |
| `status` | varchar(16) | no | `'FIRING'` | CHECK: FIRING, ACKNOWLEDGED, RESOLVED | 💡 values |
| `triggered_at` | timestamptz | no |  |  |  |
| `resolved_at` | timestamptz | yes |  |  |  |
| `metadata` | jsonb | no | `'{}'::jsonb` |  |  |

Extra constraints / indexes:

- `CREATE INDEX ix_alerts_project_id_status ON alerts (project_id, status);`

## cost_records

📋 **Cost** · Actual cost of a period, imported from AWS, compared with estimates.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `aws_account_id` | uuid | no |  | FK → aws_accounts.id |  |
| `period_start` | date | no |  |  |  |
| `period_end` | date | no |  |  |  |
| `amount` | numeric(12,2) | no |  |  |  |
| `currency` | char(3) | no | `'USD'` |  |  |
| `source` | varchar(32) | no |  | CHECK: COST_EXPLORER, MANUAL | 💡 values |
| `metadata` | jsonb | no | `'{}'::jsonb` |  |  |
| `created_at` | timestamptz | no | `now()` |  |  |

## incidents

📋 **Incident** · A detected problem on a project/deployment.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `deployment_id` | uuid | yes |  | FK → deployments.id |  |
| `alert_id` | uuid | yes |  | FK → alerts.id |  |
| `title` | varchar(255) | no |  |  |  |
| `description` | text | yes |  |  |  |
| `severity` | varchar(16) | no |  | CHECK: LOW, MEDIUM, HIGH, CRITICAL |  |
| `status` | varchar(16) | no | `'OPEN'` | CHECK: OPEN, INVESTIGATING, MITIGATING, RESOLVED, CLOSED |  |
| `detected_at` | timestamptz | no |  |  |  |
| `resolved_at` | timestamptz | yes |  |  |  |
| `root_cause` | text | yes |  |  |  |
| `diagnosis` | text | yes |  |  |  |
| `metadata` | jsonb | no | `'{}'::jsonb` |  |  |

Extra constraints / indexes:

- `CREATE INDEX ix_incidents_project_id_status ON incidents (project_id, status);`

## agent_runs

📋 **AI Agents** · One execution of an AI agent. Trace for analysis, architecture, diagnosis.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `project_id` | uuid | no |  | FK → projects.id |  |
| `deployment_id` | uuid | yes |  | FK → deployments.id | create as plain uuid in M3, add FK in M5 (ADR-012) |
| `incident_id` | uuid | yes |  | FK → incidents.id | create as plain uuid in M3, add FK in M7 (ADR-012) |
| `agent_type` | varchar(24) | no |  | CHECK: ANALYSIS, ARCHITECTURE, DIAGNOSIS, HEALING | 💡 values |
| `model` | varchar(64) | yes |  |  |  |
| `status` | varchar(16) | no | `'QUEUED'` | CHECK: QUEUED, RUNNING, SUCCESS, BLOCKED, FAILED, TIMED_OUT, CANCELLED |  |
| `created_at` | timestamptz | no | `now()` |  | **New** · 💡 (P3) |
| `started_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `input_data` | jsonb | yes |  |  | redacted, no secrets |
| `output_data` | jsonb | yes |  |  |  |
| `usage` | jsonb | yes |  |  | **New** · 💡 tokens, latency, cost (P9) |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  |  |

## agent_tasks

📋 **AI Agents** · Ordered step inside an agent run (fetch, detect, validate ...).

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `agent_run_id` | uuid | no |  | FK → agent_runs.id |  |
| `task_type` | varchar(32) | no |  |  |  |
| `status` | varchar(16) | no | `'QUEUED'` | CHECK: QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED |  |
| `step_order` | integer | no |  | CHECK > 0 |  |
| `created_at` | timestamptz | no | `now()` |  | **New** · 💡 (P3) |
| `input_data` | jsonb | yes |  |  |  |
| `output_data` | jsonb | yes |  |  | attempt number for retries |
| `started_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  |  |

Extra constraints / indexes:

- `ALTER TABLE agent_tasks ADD CONSTRAINT uq_agent_tasks_agent_run_id_step_order UNIQUE (agent_run_id, step_order);`

## healing_actions

📋 **Incident** · Corrective action proposed for an incident.

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `incident_id` | uuid | no |  | FK → incidents.id |  |
| `agent_run_id` | uuid | yes |  | FK → agent_runs.id |  |
| `action_type` | varchar(32) | no |  |  |  |
| `description` | text | no |  |  |  |
| `risk_level` | varchar(8) | no |  | CHECK: LOW, MEDIUM, HIGH |  |
| `status` | varchar(20) | no | `'PROPOSED'` | CHECK: PROPOSED, PENDING_APPROVAL, APPROVED, REJECTED, EXECUTING, SUCCEEDED, FAILED | 💡 values |
| `proposed_at` | timestamptz | no | `now()` |  |  |
| `approved_at` | timestamptz | yes |  |  |  |
| `executed_at` | timestamptz | yes |  |  |  |
| `completed_at` | timestamptz | yes |  |  |  |
| `result` | text | yes |  |  |  |
| `error_code` | varchar(64) | yes |  |  |  |
| `error_message` | text | yes |  |  |  |
| `action_data` | jsonb | no | `'{}'::jsonb` |  |  |

## approvals

📋 **Incident** · Human decision gate. Generalized to deployments (ADR-011).

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `healing_action_id` | uuid | yes |  | UNIQUE; FK → healing_actions.id | exactly one of the two subjects |
| `deployment_id` | uuid | yes |  | FK → deployments.id | **New** · 💡 (P6) |
| `requested_by` | uuid | no |  | FK → users.id |  |
| `approved_by` | uuid | yes |  | FK → users.id |  |
| `status` | varchar(16) | no | `'PENDING'` | CHECK: PENDING, APPROVED, REJECTED, EXPIRED |  |
| `reason` | text | yes |  |  |  |
| `requested_at` | timestamptz | no | `now()` |  |  |
| `decided_at` | timestamptz | yes |  |  |  |

Extra constraints / indexes:

- `ALTER TABLE approvals ADD CONSTRAINT ck_approvals_one_subject CHECK (num_nonnulls(healing_action_id, deployment_id) = 1);`

## audit_logs

💡 **Audit** · Append-only trail of sensitive actions (README 'Audit' domain, absent in ERD).

| Column | Type | Null | Default | Key / constraint | Notes |
|---|---|:-:|---|---|---|
| `id` | uuid | no |  | PK |  |
| `team_id` | uuid | no |  | FK → teams.id |  |
| `actor_user_id` | uuid | yes |  | FK → users.id | NULL = system / agent |
| `action` | varchar(64) | no |  |  | e.g. DEPLOYMENT_APPROVED |
| `entity_type` | varchar(64) | no |  |  |  |
| `entity_id` | uuid | yes |  |  |  |
| `correlation_id` | varchar(64) | yes |  |  |  |
| `metadata` | jsonb | no | `'{}'::jsonb` |  | no secrets |
| `created_at` | timestamptz | no | `now()` |  |  |

Extra constraints / indexes:

- `CREATE INDEX ix_audit_logs_team_id_created_at ON audit_logs (team_id, created_at DESC);`
