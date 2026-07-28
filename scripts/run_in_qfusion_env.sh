#!/usr/bin/env bash

set -euo pipefail

readonly script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly repository_root="$(cd -- "${script_directory}/.." && pwd -P)"

if [[ ! -f "${repository_root}/PROJECT_TASKBOOK.md" || ! -f "${repository_root}/pyproject.toml" ]]; then
  echo "Refusing to run outside the QFusion repository." >&2
  exit 2
fi

if (($# == 0)); then
  echo "Usage: $0 COMMAND [ARG ...]" >&2
  exit 2
fi

isolated_ci_environment=()
if [[ "${CI:-}" == "true" ]]; then
  isolated_ci_environment+=("CI=true")
fi
readonly -a isolated_ci_environment

/bin/mkdir -p \
  "${repository_root}/.cache/corepack" \
  "${repository_root}/.cache/coverage" \
  "${repository_root}/.cache/home" \
  "${repository_root}/.cache/mypy" \
  "${repository_root}/.cache/pip" \
  "${repository_root}/.cache/playwright" \
  "${repository_root}/.cache/pnpm/cache" \
  "${repository_root}/.cache/pnpm/state" \
  "${repository_root}/.cache/pnpm/store" \
  "${repository_root}/.cache/ruff" \
  "${repository_root}/.cache/uv" \
  "${repository_root}/.cache/xdg/cache" \
  "${repository_root}/.cache/xdg/config" \
  "${repository_root}/.cache/xdg/data" \
  "${repository_root}/.cache/xdg/state" \
  "${repository_root}/.tmp" \
  "${repository_root}/.toolchains/bin" \
  "${repository_root}/.toolchains/cargo" \
  "${repository_root}/.toolchains/python" \
  "${repository_root}/.toolchains/rustup" \
  "${repository_root}/.toolchains/uv-tools"

readonly isolated_path="${repository_root}/.toolchains/bin:${repository_root}/.toolchains/node/bin:${repository_root}/.toolchains/cargo/bin:${repository_root}/.venv/bin:/usr/bin:/bin"

exec /usr/bin/env -i \
  "${isolated_ci_environment[@]}" \
  CARGO_HOME="${repository_root}/.toolchains/cargo" \
  COREPACK_HOME="${repository_root}/.cache/corepack" \
  COVERAGE_FILE="${repository_root}/.cache/coverage/.coverage" \
  GIT_CONFIG_GLOBAL=/dev/null \
  GIT_CONFIG_NOSYSTEM=1 \
  HOME="${repository_root}/.cache/home" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  LOGNAME=qfusion \
  MYPY_CACHE_DIR="${repository_root}/.cache/mypy" \
  NPM_CONFIG_CACHE="${repository_root}/.cache/pnpm/cache" \
  NPM_CONFIG_GLOBALCONFIG=/dev/null \
  NPM_CONFIG_STATE_DIR="${repository_root}/.cache/pnpm/state" \
  NPM_CONFIG_STORE_DIR="${repository_root}/.cache/pnpm/store" \
  NPM_CONFIG_USERCONFIG="${repository_root}/.npmrc" \
  PATH="${isolated_path}" \
  PIP_CACHE_DIR="${repository_root}/.cache/pip" \
  PIP_CONFIG_FILE=/dev/null \
  PLAYWRIGHT_BROWSERS_PATH="${repository_root}/.cache/playwright" \
  PNPM_HOME="${repository_root}/.toolchains/bin" \
  PYTHONPYCACHEPREFIX="${repository_root}/.cache/python/pycache" \
  QFUSION_CACHE_DIR="${repository_root}/.cache" \
  QFUSION_ISOLATED=1 \
  QFUSION_REPOSITORY_ROOT="${repository_root}" \
  RUFF_CACHE_DIR="${repository_root}/.cache/ruff" \
  RUSTUP_AUTO_INSTALL=0 \
  RUSTUP_HOME="${repository_root}/.toolchains/rustup" \
  RUSTUP_INIT_SKIP_PATH_CHECK=yes \
  RUSTUP_NO_UPDATE_CHECK=1 \
  RUSTUP_TOOLCHAIN=1.97.1 \
  SHELL=/bin/bash \
  TMPDIR="${repository_root}/.tmp" \
  TZ=UTC \
  USER=qfusion \
  UV_CACHE_DIR="${repository_root}/.cache/uv" \
  UV_NO_SYSTEM_CONFIG=1 \
  UV_PROJECT_ENVIRONMENT="${repository_root}/.venv" \
  UV_PYTHON_INSTALL_DIR="${repository_root}/.toolchains/python" \
  UV_TOOL_BIN_DIR="${repository_root}/.toolchains/bin" \
  UV_TOOL_DIR="${repository_root}/.toolchains/uv-tools" \
  XDG_CACHE_HOME="${repository_root}/.cache/xdg/cache" \
  XDG_CONFIG_HOME="${repository_root}/.cache/xdg/config" \
  XDG_DATA_HOME="${repository_root}/.cache/xdg/data" \
  XDG_STATE_HOME="${repository_root}/.cache/xdg/state" \
  "$@"
