#!/usr/bin/env bash

set -euo pipefail

readonly script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly repository_root="$(cd -- "${script_directory}/.." && pwd -P)"
readonly isolated_runner="${script_directory}/run_in_qfusion_env.sh"

"${script_directory}/install_tools_linux.sh"
"${isolated_runner}" uv sync --locked --all-extras
"${isolated_runner}" uv run --locked python scripts/check_pnpm_isolation.py
"${isolated_runner}" uv run --locked python scripts/export_openapi.py
"${isolated_runner}" pnpm install --frozen-lockfile
"${isolated_runner}" pnpm generate:client
"${isolated_runner}" pnpm --dir apps/desktop tauri icon src-tauri/app-icon.svg --output src-tauri/icons

echo "QFusion workspace setup completed."
