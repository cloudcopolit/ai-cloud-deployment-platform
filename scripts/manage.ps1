param (
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "test", "logs", "reset", "help")]
    [string]$Action = "help"
)

switch ($Action) {
    "up" {
        Write-Host "==> Starting CloudPilot stack in background..." -ForegroundColor Cyan
        docker compose up --build -d
    }
    "down" {
        Write-Host "==> Stopping CloudPilot stack..." -ForegroundColor Yellow
        docker compose down
    }
    "test" {
        # The gates are a POSIX script (Git Bash provides `sh` on Windows).
        Write-Host "==> Running every quality gate (scripts/check.sh)..." -ForegroundColor Cyan
        sh "$PSScriptRoot/check.sh" all
    }
    "logs" {
        docker compose logs -f
    }
    "reset" {
        Write-Host "==> Resetting stack and wiping named volumes..." -ForegroundColor Red
        docker compose down --volumes --remove-orphans
    }
    default {
        Write-Host "Usage: .\scripts\manage.ps1 [up|down|test|logs|reset]" -ForegroundColor Green
    }
}
