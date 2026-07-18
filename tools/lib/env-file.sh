#!/usr/bin/env bash
# Safe helpers for reading selected values from a dotenv file without eval/source.

if [[ "${_hfl_env_file_lib_loaded:-0}" == "1" ]]; then
	return 0
fi
_hfl_env_file_lib_loaded=1

HFL_ENV_FILE="${HFL_ENV_FILE:-}"

hfl_env_select_repo_file() {
	local root=$1
	if [[ -f "${root}/.env" ]]; then
		HFL_ENV_FILE="${root}/.env"
	else
		HFL_ENV_FILE="${root}/.env.example"
	fi
}

hfl_env_read() {
	local key=$1 line value
	[[ -n "${HFL_ENV_FILE}" && -f "${HFL_ENV_FILE}" ]] || return 0
	line="$(grep -E "^${key}=" "${HFL_ENV_FILE}" 2>/dev/null | head -1 || true)"
	[[ -n "${line}" ]] || return 0
	value="${line#*=}"
	value="${value%$'\r'}"
	if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
		value="${value:1:${#value}-2}"
	elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
		value="${value:1:${#value}-2}"
	fi
	printf '%s' "${value}"
}

hfl_env_load_default() {
	local key=$1 value
	[[ -z "${!key:-}" ]] || return 0
	value="$(hfl_env_read "${key}")"
	[[ -n "${value}" ]] || return 0
	printf -v "${key}" '%s' "${value}"
	export "${key}"
}
