param (
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "test", "e2e", "logs", "reset", "help")]
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
        Write-Host "==> Running backend test suite in Docker..." -ForegroundColor Cyan
        docker compose run --rm backend-tests
        Write-Host "==> Running frontend test suite in Docker..." -ForegroundColor Cyan
        docker compose run --rm frontend pnpm test
    }
    "e2e" {
        Write-Host "==> Running Playwright E2E tests..." -ForegroundColor Cyan
        docker compose run --rm frontend pnpm test:e2e
    }
    "logs" {
        docker compose logs -f
    }
    "reset" {
        Write-Host "==> Resetting stack and wiping named volumes..." -ForegroundColor Red
        docker compose down --volumes --remove-orphans
    }
    default {
        Write-Host "Usage: .\scripts\manage.ps1 [up|down|test|e2e|logs|reset]" -ForegroundColor Green
    }
}
