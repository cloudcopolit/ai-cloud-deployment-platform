# ERD (generated)

> Mermaid diagrams generated from the schema spec (27 tables). The original editable ERD is `../diagrams/CloudPilot_ERD.drawio`.
> Dashed/optional links (`|o`) are nullable FKs. `plans`, `subscriptions`, `audit_logs` and the new columns are proposals/gaps listed in `04` §7.

## 1. Overview (keys only)

```mermaid
erDiagram
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    teams {
        uuid id PK
    }
    team_members {
        uuid team_id PK,FK
        uuid user_id PK,FK
    }
    plans {
        uuid id PK
        varchar code UK
    }
    subscriptions {
        uuid id PK
        uuid team_id FK
        uuid plan_id FK
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    repositories {
        uuid id PK
        uuid project_id FK
    }
    branches {
        uuid id PK
        uuid repository_id FK
    }
    commits {
        uuid id PK
        uuid repository_id FK
        uuid branch_id FK
    }
    repository_analyses {
        uuid id PK
        uuid repository_id FK
        uuid commit_id FK
        uuid requested_by FK
    }
    services {
        uuid id PK
        uuid analysis_id FK
    }
    architectures {
        uuid id PK
        uuid project_id FK
    }
    architecture_versions {
        uuid id PK
        uuid architecture_id FK
        uuid source_analysis_id FK
        uuid created_by FK
    }
    cost_estimates {
        uuid id PK
        uuid project_id FK
        uuid architecture_version_id FK
    }
    aws_accounts {
        uuid id PK
        uuid team_id FK
    }
    deployments {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        uuid commit_id FK
        uuid architecture_version_id FK
        uuid aws_account_id FK
        uuid created_by FK
    }
    deployment_steps {
        uuid id PK
        uuid deployment_id FK
    }
    infrastructure_resources {
        uuid id PK
        uuid deployment_id FK
    }
    monitoring_configs {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
    }
    alerts {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
    }
    cost_records {
        uuid id PK
        uuid project_id FK
        uuid aws_account_id FK
    }
    incidents {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid alert_id FK
    }
    agent_runs {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid incident_id FK
    }
    agent_tasks {
        uuid id PK
        uuid agent_run_id FK
    }
    healing_actions {
        uuid id PK
        uuid incident_id FK
        uuid agent_run_id FK
    }
    approvals {
        uuid id PK
        uuid healing_action_id FK,UK
        uuid deployment_id FK
        uuid requested_by FK
        uuid approved_by FK
    }
    audit_logs {
        uuid id PK
        uuid team_id FK
        uuid actor_user_id FK
    }
    teams ||--o{ team_members : "team_id"
    users ||--o{ team_members : "user_id"
    teams ||--o{ subscriptions : "team_id"
    plans ||--o{ subscriptions : "plan_id"
    teams ||--o{ projects : "team_id"
    projects ||--o{ repositories : "project_id"
    repositories ||--o{ branches : "repository_id"
    repositories ||--o{ commits : "repository_id"
    branches ||--o{ commits : "branch_id"
    repositories ||--o{ repository_analyses : "repository_id"
    commits ||--o{ repository_analyses : "commit_id"
    users |o--o{ repository_analyses : "requested_by"
    repository_analyses ||--o{ services : "analysis_id"
    projects ||--o{ architectures : "project_id"
    architectures ||--o{ architecture_versions : "architecture_id"
    repository_analyses |o--o{ architecture_versions : "source_analysis_id"
    users |o--o{ architecture_versions : "created_by"
    projects ||--o{ cost_estimates : "project_id"
    architecture_versions ||--o{ cost_estimates : "architecture_version_id"
    teams ||--o{ aws_accounts : "team_id"
    projects ||--o{ deployments : "project_id"
    repositories ||--o{ deployments : "repository_id"
    commits ||--o{ deployments : "commit_id"
    architecture_versions ||--o{ deployments : "architecture_version_id"
    aws_accounts ||--o{ deployments : "aws_account_id"
    users |o--o{ deployments : "created_by"
    deployments ||--o{ deployment_steps : "deployment_id"
    deployments ||--o{ infrastructure_resources : "deployment_id"
    projects ||--o{ monitoring_configs : "project_id"
    deployments ||--o{ monitoring_configs : "deployment_id"
    projects ||--o{ alerts : "project_id"
    deployments ||--o{ alerts : "deployment_id"
    projects ||--o{ cost_records : "project_id"
    aws_accounts ||--o{ cost_records : "aws_account_id"
    projects ||--o{ incidents : "project_id"
    deployments |o--o{ incidents : "deployment_id"
    alerts |o--o{ incidents : "alert_id"
    projects ||--o{ agent_runs : "project_id"
    deployments |o--o{ agent_runs : "deployment_id"
    incidents |o--o{ agent_runs : "incident_id"
    agent_runs ||--o{ agent_tasks : "agent_run_id"
    incidents ||--o{ healing_actions : "incident_id"
    agent_runs |o--o{ healing_actions : "agent_run_id"
    healing_actions |o--o| approvals : "healing_action_id"
    deployments |o--o{ approvals : "deployment_id"
    users ||--o{ approvals : "requested_by"
    users |o--o{ approvals : "approved_by"
    teams ||--o{ audit_logs : "team_id"
    users |o--o{ audit_logs : "actor_user_id"
```

## 2. Identity

Tables: `users`, `teams`, `team_members`

```mermaid
erDiagram
    users {
        uuid id PK
        varchar github_user_id UK
        varchar name
        varchar email UK
        text avatar_url
        timestamp created_at
        timestamp updated_at
    }
    teams {
        uuid id PK
        varchar name
        timestamp created_at
        timestamp updated_at
    }
    team_members {
        uuid team_id PK,FK
        uuid user_id PK,FK
        varchar role
        timestamp joined_at
    }
    teams ||--o{ team_members : "team_id"
    users ||--o{ team_members : "user_id"
```

## 3. Subscription

Tables: `plans`, `subscriptions` · context: `teams`

```mermaid
erDiagram
    plans {
        uuid id PK
        varchar code UK
        varchar name
        numeric price_monthly
        jsonb limits
        timestamp created_at
    }
    subscriptions {
        uuid id PK
        uuid team_id FK
        uuid plan_id FK
        varchar status
        timestamp started_at
        timestamp ended_at
        timestamp created_at
    }
    teams {
        uuid id PK
    }
    teams ||--o{ subscriptions : "team_id"
    plans ||--o{ subscriptions : "plan_id"
```

## 4. Project

Tables: `projects` · context: `teams`

```mermaid
erDiagram
    projects {
        uuid id PK
        uuid team_id FK
        varchar name
        text description
        varchar status
        timestamp created_at
        timestamp updated_at
    }
    teams {
        uuid id PK
    }
    teams ||--o{ projects : "team_id"
```

## 5. Source Control

Tables: `repositories`, `branches`, `commits` · context: `projects`

```mermaid
erDiagram
    repositories {
        uuid id PK
        uuid project_id FK
        varchar github_repository_id
        varchar owner
        varchar name
        text url
        varchar default_branch
        timestamp connected_at
        timestamp updated_at
    }
    branches {
        uuid id PK
        uuid repository_id FK
        varchar name
        boolean is_default
        boolean is_deployment_branch
        timestamp created_at
        timestamp updated_at
    }
    commits {
        uuid id PK
        uuid repository_id FK
        uuid branch_id FK
        varchar sha
        text message
        varchar author_name
        varchar author_email
        timestamp committed_at
        timestamp detected_at
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    projects ||--o{ repositories : "project_id"
    repositories ||--o{ branches : "repository_id"
    repositories ||--o{ commits : "repository_id"
    branches ||--o{ commits : "branch_id"
```

## 6. Analysis

Tables: `repository_analyses`, `services` · context: `repositories`, `commits`, `users`

```mermaid
erDiagram
    repository_analyses {
        uuid id PK
        uuid repository_id FK
        uuid commit_id FK
        varchar status
        timestamp created_at
        timestamp started_at
        timestamp completed_at
        uuid requested_by FK
        varchar report_schema_version
        varchar error_code
        text error_message
        jsonb analysis_data
    }
    services {
        uuid id PK
        uuid analysis_id FK
        varchar name
        varchar service_type
        varchar language
        varchar framework
        varchar path
        integer port
        jsonb metadata
        timestamp created_at
    }
    repositories {
        uuid id PK
        uuid project_id FK
    }
    commits {
        uuid id PK
        uuid repository_id FK
        uuid branch_id FK
    }
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    repositories ||--o{ repository_analyses : "repository_id"
    commits ||--o{ repository_analyses : "commit_id"
    users |o--o{ repository_analyses : "requested_by"
    repository_analyses ||--o{ services : "analysis_id"
    repositories ||--o{ commits : "repository_id"
```

## 7. Architecture

Tables: `architectures`, `architecture_versions` · context: `projects`, `repository_analyses`, `users`

```mermaid
erDiagram
    architectures {
        uuid id PK
        uuid project_id FK
        varchar name
        varchar status
        timestamp created_at
        timestamp updated_at
    }
    architecture_versions {
        uuid id PK
        uuid architecture_id FK
        integer version_number
        uuid source_analysis_id FK
        varchar status
        jsonb architecture_data
        uuid created_by FK
        timestamp created_at
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    repository_analyses {
        uuid id PK
        uuid repository_id FK
        uuid commit_id FK
        uuid requested_by FK
    }
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    projects ||--o{ architectures : "project_id"
    architectures ||--o{ architecture_versions : "architecture_id"
    repository_analyses |o--o{ architecture_versions : "source_analysis_id"
    users |o--o{ architecture_versions : "created_by"
    users |o--o{ repository_analyses : "requested_by"
```

## 8. Cost

Tables: `cost_estimates`, `cost_records` · context: `projects`, `architecture_versions`, `aws_accounts`

```mermaid
erDiagram
    cost_estimates {
        uuid id PK
        uuid project_id FK
        uuid architecture_version_id FK
        numeric estimated_monthly_cost
        char currency
        jsonb breakdown
        timestamp calculated_at
    }
    cost_records {
        uuid id PK
        uuid project_id FK
        uuid aws_account_id FK
        date period_start
        date period_end
        numeric amount
        char currency
        varchar source
        jsonb metadata
        timestamp created_at
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    architecture_versions {
        uuid id PK
        uuid architecture_id FK
        uuid source_analysis_id FK
        uuid created_by FK
    }
    aws_accounts {
        uuid id PK
        uuid team_id FK
    }
    projects ||--o{ cost_estimates : "project_id"
    architecture_versions ||--o{ cost_estimates : "architecture_version_id"
    projects ||--o{ cost_records : "project_id"
    aws_accounts ||--o{ cost_records : "aws_account_id"
```

## 9. AWS

Tables: `aws_accounts` · context: `teams`

```mermaid
erDiagram
    aws_accounts {
        uuid id PK
        uuid team_id FK
        varchar aws_account_id
        text role_arn
        text readonly_role_arn
        varchar external_id
        varchar default_region
        varchar status
        timestamp connected_at
        timestamp last_verified_at
    }
    teams {
        uuid id PK
    }
    teams ||--o{ aws_accounts : "team_id"
```

## 10. Deployment

Tables: `deployments`, `deployment_steps`, `infrastructure_resources` · context: `projects`, `repositories`, `commits`, `architecture_versions`, `aws_accounts`, `users`

```mermaid
erDiagram
    deployments {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        uuid commit_id FK
        uuid architecture_version_id FK
        uuid aws_account_id FK
        varchar status
        varchar trigger_type
        timestamp created_at
        timestamp started_at
        timestamp completed_at
        varchar error_code
        text error_message
        uuid created_by FK
    }
    deployment_steps {
        uuid id PK
        uuid deployment_id FK
        varchar step_type
        integer step_order
        varchar status
        timestamp created_at
        timestamp started_at
        timestamp completed_at
        varchar error_code
        text error_message
        jsonb input_data
        jsonb output_data
    }
    infrastructure_resources {
        uuid id PK
        uuid deployment_id FK
        varchar resource_type
        varchar resource_name
        varchar aws_resource_id
        text aws_arn
        varchar region
        varchar status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    repositories {
        uuid id PK
        uuid project_id FK
    }
    commits {
        uuid id PK
        uuid repository_id FK
        uuid branch_id FK
    }
    architecture_versions {
        uuid id PK
        uuid architecture_id FK
        uuid source_analysis_id FK
        uuid created_by FK
    }
    aws_accounts {
        uuid id PK
        uuid team_id FK
    }
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    projects ||--o{ deployments : "project_id"
    repositories ||--o{ deployments : "repository_id"
    commits ||--o{ deployments : "commit_id"
    architecture_versions ||--o{ deployments : "architecture_version_id"
    aws_accounts ||--o{ deployments : "aws_account_id"
    users |o--o{ deployments : "created_by"
    deployments ||--o{ deployment_steps : "deployment_id"
    deployments ||--o{ infrastructure_resources : "deployment_id"
    projects ||--o{ repositories : "project_id"
    repositories ||--o{ commits : "repository_id"
    users |o--o{ architecture_versions : "created_by"
```

## 11. Monitoring

Tables: `monitoring_configs`, `alerts` · context: `projects`, `deployments`

```mermaid
erDiagram
    monitoring_configs {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        boolean enabled
        jsonb configuration
        timestamp created_at
        timestamp updated_at
    }
    alerts {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        varchar severity
        varchar source
        varchar metric_name
        numeric threshold
        numeric actual_value
        varchar status
        timestamp triggered_at
        timestamp resolved_at
        jsonb metadata
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    deployments {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        uuid commit_id FK
        uuid architecture_version_id FK
        uuid aws_account_id FK
        uuid created_by FK
    }
    projects ||--o{ monitoring_configs : "project_id"
    deployments ||--o{ monitoring_configs : "deployment_id"
    projects ||--o{ alerts : "project_id"
    deployments ||--o{ alerts : "deployment_id"
    projects ||--o{ deployments : "project_id"
```

## 12. Incident

Tables: `incidents`, `healing_actions`, `approvals` · context: `projects`, `deployments`, `alerts`, `agent_runs`, `users`

```mermaid
erDiagram
    incidents {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid alert_id FK
        varchar title
        text description
        varchar severity
        varchar status
        timestamp detected_at
        timestamp resolved_at
        text root_cause
        text diagnosis
        jsonb metadata
    }
    healing_actions {
        uuid id PK
        uuid incident_id FK
        uuid agent_run_id FK
        varchar action_type
        text description
        varchar risk_level
        varchar status
        timestamp proposed_at
        timestamp approved_at
        timestamp executed_at
        timestamp completed_at
        text result
        varchar error_code
        text error_message
        jsonb action_data
    }
    approvals {
        uuid id PK
        uuid healing_action_id FK,UK
        uuid deployment_id FK
        uuid requested_by FK
        uuid approved_by FK
        varchar status
        text reason
        timestamp requested_at
        timestamp decided_at
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    deployments {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        uuid commit_id FK
        uuid architecture_version_id FK
        uuid aws_account_id FK
        uuid created_by FK
    }
    alerts {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
    }
    agent_runs {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid incident_id FK
    }
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    projects ||--o{ incidents : "project_id"
    deployments |o--o{ incidents : "deployment_id"
    alerts |o--o{ incidents : "alert_id"
    incidents ||--o{ healing_actions : "incident_id"
    agent_runs |o--o{ healing_actions : "agent_run_id"
    healing_actions |o--o| approvals : "healing_action_id"
    deployments |o--o{ approvals : "deployment_id"
    users ||--o{ approvals : "requested_by"
    users |o--o{ approvals : "approved_by"
    projects ||--o{ deployments : "project_id"
    users |o--o{ deployments : "created_by"
    projects ||--o{ alerts : "project_id"
    deployments ||--o{ alerts : "deployment_id"
    projects ||--o{ agent_runs : "project_id"
    deployments |o--o{ agent_runs : "deployment_id"
    incidents |o--o{ agent_runs : "incident_id"
```

## 13. AI Agents

Tables: `agent_runs`, `agent_tasks` · context: `projects`, `deployments`, `incidents`

```mermaid
erDiagram
    agent_runs {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid incident_id FK
        varchar agent_type
        varchar model
        varchar status
        timestamp created_at
        timestamp started_at
        timestamp completed_at
        jsonb input_data
        jsonb output_data
        jsonb usage
        varchar error_code
        text error_message
    }
    agent_tasks {
        uuid id PK
        uuid agent_run_id FK
        varchar task_type
        varchar status
        integer step_order
        timestamp created_at
        jsonb input_data
        jsonb output_data
        timestamp started_at
        timestamp completed_at
        varchar error_code
        text error_message
    }
    projects {
        uuid id PK
        uuid team_id FK
    }
    deployments {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        uuid commit_id FK
        uuid architecture_version_id FK
        uuid aws_account_id FK
        uuid created_by FK
    }
    incidents {
        uuid id PK
        uuid project_id FK
        uuid deployment_id FK
        uuid alert_id FK
    }
    projects ||--o{ agent_runs : "project_id"
    deployments |o--o{ agent_runs : "deployment_id"
    incidents |o--o{ agent_runs : "incident_id"
    agent_runs ||--o{ agent_tasks : "agent_run_id"
    projects ||--o{ deployments : "project_id"
    projects ||--o{ incidents : "project_id"
    deployments |o--o{ incidents : "deployment_id"
```

## 14. Audit

Tables: `audit_logs` · context: `teams`, `users`

```mermaid
erDiagram
    audit_logs {
        uuid id PK
        uuid team_id FK
        uuid actor_user_id FK
        varchar action
        varchar entity_type
        uuid entity_id
        varchar correlation_id
        jsonb metadata
        timestamp created_at
    }
    teams {
        uuid id PK
    }
    users {
        uuid id PK
        varchar github_user_id UK
        varchar email UK
    }
    teams ||--o{ audit_logs : "team_id"
    users |o--o{ audit_logs : "actor_user_id"
```

