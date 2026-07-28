set dotenv-load := false
set shell := ["bash", "-cu"]

backend_manifest := "pyproject.toml"
desktop_dir := "apps/desktop"
tauri_manifest := "apps/desktop/src-tauri/Cargo.toml"
isolated_runner := "./scripts/run_in_qfusion_env.sh"

# Install workspace dependencies and regenerate API types.
setup:
    ./scripts/bootstrap_linux.sh

# Run Python, TypeScript, formatting, and Rust lint checks.
lint:
    {{isolated_runner}} uv run ruff check services/backend scripts
    {{isolated_runner}} pnpm --dir {{desktop_dir}} lint
    {{isolated_runner}} cargo fmt --manifest-path {{tauri_manifest}} --all --check
    {{isolated_runner}} cargo clippy --locked --manifest-path {{tauri_manifest}} --all-targets -- -D warnings

# Run strict backend, frontend, and Rust type/build checks.
typecheck:
    {{isolated_runner}} uv run mypy
    {{isolated_runner}} pnpm --dir {{desktop_dir}} typecheck
    {{isolated_runner}} pnpm --filter @qfusion/generated-client typecheck
    {{isolated_runner}} cargo check --locked --manifest-path {{tauri_manifest}} --all-targets

# Run all non-E2E unit tests.
test: test-backend test-frontend test-rust

test-backend:
    {{isolated_runner}} uv run pytest

test-frontend:
    {{isolated_runner}} pnpm --dir {{desktop_dir}} test

test-rust:
    {{isolated_runner}} cargo test --locked --manifest-path {{tauri_manifest}}

test-e2e:
    {{isolated_runner}} pnpm --dir {{desktop_dir}} test:e2e

run-backend:
    {{isolated_runner}} uv run qfusion-backend

run-desktop:
    {{isolated_runner}} pnpm --dir {{desktop_dir}} tauri dev

build-backend:
    {{isolated_runner}} uv run python scripts/build_backend.py

# Must be run in Windows PowerShell with the Windows build prerequisites.
build-windows:
    pwsh -NoProfile -File scripts/build_windows.ps1
