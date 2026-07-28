#!/usr/bin/env bash

set -euo pipefail

readonly script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly repository_root="$(cd -- "${script_directory}/.." && pwd -P)"
readonly version_file="${script_directory}/toolchain-versions.json"

if [[ "${QFUSION_ISOLATED:-}" != "1" ]]; then
  exec "${script_directory}/run_in_qfusion_env.sh" "$0" "$@"
fi

blocked() {
  echo "BLOCKED_BY_HOST_ISOLATION" >&2
  echo "$1" >&2
  exit 1
}

for required_tool in curl install mkdir mv python3 sha256sum tar uname; do
  if ! command -v "${required_tool}" >/dev/null 2>&1; then
    blocked "Missing read-only bootstrap tool: ${required_tool}"
  fi
done

case "$(uname -m)" in
  aarch64 | arm64)
    readonly platform_key="linux-arm64"
    ;;
  x86_64 | amd64)
    readonly platform_key="linux-x64"
    ;;
  *)
    blocked "Unsupported Linux architecture: $(uname -m)"
    ;;
esac

mapfile -t tool_configuration < <(
  python3 - "${version_file}" "${platform_key}" <<'PY'
import json
import sys
from pathlib import Path

configuration = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
platform = sys.argv[2]
tools = configuration["tools"]
values = [
    tools["node"]["version"],
    tools["node"]["assets"][platform]["url"],
    tools["node"]["assets"][platform]["sha256"],
    tools["uv"]["version"],
    tools["uv"]["assets"][platform]["url"],
    tools["uv"]["assets"][platform]["sha256"],
    tools["just"]["version"],
    tools["just"]["assets"][platform]["url"],
    tools["just"]["assets"][platform]["sha256"],
    tools["pnpm"]["version"],
    tools["rust"]["version"],
    tools["rustup"]["version"],
    tools["rustup"]["assets"][platform]["host"],
    tools["rustup"]["assets"][platform]["url"],
    tools["rustup"]["assets"][platform]["sha256"],
]
print(*values, sep="\n")
PY
)

if ((${#tool_configuration[@]} != 15)); then
  blocked "Invalid toolchain version configuration."
fi

readonly node_version="${tool_configuration[0]}"
readonly node_url="${tool_configuration[1]}"
readonly node_sha256="${tool_configuration[2]}"
readonly uv_version="${tool_configuration[3]}"
readonly uv_url="${tool_configuration[4]}"
readonly uv_sha256="${tool_configuration[5]}"
readonly just_version="${tool_configuration[6]}"
readonly just_url="${tool_configuration[7]}"
readonly just_sha256="${tool_configuration[8]}"
readonly pnpm_version="${tool_configuration[9]}"
readonly rust_version="${tool_configuration[10]}"
readonly rustup_version="${tool_configuration[11]}"
readonly rust_host="${tool_configuration[12]}"
readonly rustup_url="${tool_configuration[13]}"
readonly rustup_sha256="${tool_configuration[14]}"

readonly download_directory="${repository_root}/.cache/downloads"
readonly local_bin_directory="${repository_root}/.toolchains/bin"
mkdir -p "${download_directory}" "${local_bin_directory}" "${repository_root}/.tmp"

verify_checksum() {
  local path="$1"
  local expected_sha256="$2"
  local actual_sha256
  actual_sha256="$(sha256sum "${path}" | awk '{print $1}')"
  [[ "${actual_sha256}" == "${expected_sha256}" ]]
}

download_checked() {
  local url="$1"
  local expected_sha256="$2"
  local destination="${download_directory}/${url##*/}"

  if [[ -f "${destination}" ]]; then
    if ! verify_checksum "${destination}" "${expected_sha256}"; then
      blocked "Cached download checksum mismatch: ${destination}"
    fi
    printf '%s\n' "${destination}"
    return
  fi

  local temporary_download
  temporary_download="$(mktemp "${repository_root}/.tmp/qfusion-download.XXXXXX")"
  if ! curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
    "${url}" --output "${temporary_download}"; then
    rm -f -- "${temporary_download}"
    blocked "Unable to download project-local tool: ${url}"
  fi
  if ! verify_checksum "${temporary_download}" "${expected_sha256}"; then
    rm -f -- "${temporary_download}"
    blocked "Downloaded tool checksum mismatch: ${url}"
  fi
  mv -- "${temporary_download}" "${destination}"
  printf '%s\n' "${destination}"
}

cleanup_temporary_directory() {
  local temporary_directory="$1"
  case "${temporary_directory}" in
    "${repository_root}/.tmp/"*)
      rm -rf -- "${temporary_directory}"
      ;;
    *)
      blocked "Refusing to clean an unexpected temporary path."
      ;;
  esac
}

readonly node_binary="${repository_root}/.toolchains/node/bin/node"
if [[ -x "${node_binary}" ]]; then
  [[ "$("${node_binary}" --version)" == "v${node_version}" ]] \
    || blocked "Existing project-local Node.js version does not match ${node_version}."
elif [[ -e "${repository_root}/.toolchains/node" ]]; then
  blocked "Existing project-local Node.js directory is incomplete."
else
  node_archive="$(download_checked "${node_url}" "${node_sha256}")"
  node_extract_directory="$(mktemp -d "${repository_root}/.tmp/qfusion-node.XXXXXX")"
  tar -xJf "${node_archive}" -C "${node_extract_directory}"
  node_archive_root="${node_archive##*/}"
  node_archive_root="${node_archive_root%.tar.xz}"
  [[ -x "${node_extract_directory}/${node_archive_root}/bin/node" ]] \
    || blocked "Node.js archive did not contain the expected binary."
  mv -- "${node_extract_directory}/${node_archive_root}" \
    "${repository_root}/.toolchains/node"
  cleanup_temporary_directory "${node_extract_directory}"
fi

readonly uv_binary="${local_bin_directory}/uv"
if [[ -x "${uv_binary}" ]]; then
  [[ "$("${uv_binary}" --version)" == "uv ${uv_version}"* ]] \
    || blocked "Existing project-local uv version does not match ${uv_version}."
else
  uv_archive="$(download_checked "${uv_url}" "${uv_sha256}")"
  uv_extract_directory="$(mktemp -d "${repository_root}/.tmp/qfusion-uv.XXXXXX")"
  tar -xzf "${uv_archive}" -C "${uv_extract_directory}"
  uv_source="$(find "${uv_extract_directory}" -type f -name uv -print -quit)"
  uvx_source="$(find "${uv_extract_directory}" -type f -name uvx -print -quit)"
  [[ -n "${uv_source}" && -n "${uvx_source}" ]] \
    || blocked "uv archive did not contain the expected binaries."
  install -m 0755 "${uv_source}" "${uv_binary}"
  install -m 0755 "${uvx_source}" "${local_bin_directory}/uvx"
  cleanup_temporary_directory "${uv_extract_directory}"
fi

readonly just_binary="${local_bin_directory}/just"
if [[ -x "${just_binary}" ]]; then
  [[ "$("${just_binary}" --version)" == "just ${just_version}" ]] \
    || blocked "Existing project-local just version does not match ${just_version}."
else
  just_archive="$(download_checked "${just_url}" "${just_sha256}")"
  just_extract_directory="$(mktemp -d "${repository_root}/.tmp/qfusion-just.XXXXXX")"
  tar -xzf "${just_archive}" -C "${just_extract_directory}"
  just_source="$(find "${just_extract_directory}" -type f -name just -print -quit)"
  [[ -n "${just_source}" ]] || blocked "just archive did not contain the expected binary."
  install -m 0755 "${just_source}" "${just_binary}"
  cleanup_temporary_directory "${just_extract_directory}"
fi

readonly corepack_binary="${repository_root}/.toolchains/node/bin/corepack"
readonly pnpm_binary="${local_bin_directory}/pnpm"
[[ -x "${corepack_binary}" ]] || blocked "Pinned Node.js archive does not include Corepack."
if [[ -x "${pnpm_binary}" ]]; then
  [[ "$("${pnpm_binary}" --version)" == "${pnpm_version}" ]] \
    || blocked "Existing project-local pnpm version does not match ${pnpm_version}."
else
  "${corepack_binary}" enable --install-directory "${local_bin_directory}" pnpm
  [[ "$("${pnpm_binary}" --version)" == "${pnpm_version}" ]] \
    || blocked "Corepack did not activate the pinned pnpm ${pnpm_version}."
fi

readonly rustup_binary="${repository_root}/.toolchains/cargo/bin/rustup"
if [[ -x "${rustup_binary}" ]]; then
  [[ "$("${rustup_binary}" --version | head -n 1)" == "rustup ${rustup_version} "* ]] \
    || blocked "Existing project-local rustup version does not match ${rustup_version}."
else
  rustup_archive="$(download_checked "${rustup_url}" "${rustup_sha256}")"
  rustup_extract_directory="$(mktemp -d "${repository_root}/.tmp/qfusion-rustup.XXXXXX")"
  rustup_installer="${rustup_extract_directory}/rustup-init"
  install -m 0755 "${rustup_archive}" "${rustup_installer}"
  "${rustup_installer}" \
    --component clippy \
    --component rustfmt \
    --default-host "${rust_host}" \
    --default-toolchain "${rust_version}" \
    --no-modify-path \
    --profile minimal \
    -y
  cleanup_temporary_directory "${rustup_extract_directory}"
fi

if ! "${rustup_binary}" toolchain list | grep -Fq "${rust_version}-${rust_host}"; then
  "${rustup_binary}" toolchain install "${rust_version}" \
    --component clippy \
    --component rustfmt \
    --profile minimal
fi

readonly rustc_binary="${repository_root}/.toolchains/cargo/bin/rustc"
[[ "$("${rustc_binary}" --version)" == "rustc ${rust_version} "* ]] \
  || blocked "Project-local Rust compiler does not match ${rust_version}."

printf 'QFusion project-local tools ready: node=%s pnpm=%s uv=%s rust=%s rustup=%s just=%s\n' \
  "${node_version}" \
  "${pnpm_version}" \
  "${uv_version}" \
  "${rust_version}" \
  "${rustup_version}" \
  "${just_version}"
