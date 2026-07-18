#!/usr/bin/env bash
# Shared Docker image resolution with local reuse, mirror fallback, retries, and timeouts.

if [[ "${_hfl_docker_images_loaded:-0}" == "1" ]]; then
	return 0 2>/dev/null || exit 0
fi
_hfl_docker_images_loaded=1

HFL_DOCKER_IMAGE_SOURCE=""
HFL_DOCKER_LAST_ERROR=""

hfl_docker_normalize_mirror_host() {
	local mirror="${1:-}"
	mirror="${mirror#https://}"
	mirror="${mirror#http://}"
	mirror="${mirror%/}"
	printf '%s' "${mirror}"
}

hfl_docker_mirror_image_ref() {
	local image=$1 mirror_host=$2
	if [[ -z "${mirror_host}" ]]; then
		printf '%s' "${image}"
	elif [[ "${image}" == */* ]]; then
		printf '%s/%s' "${mirror_host}" "${image}"
	else
		printf '%s/library/%s' "${mirror_host}" "${image}"
	fi
}

hfl_docker_validate_pull_settings() {
	local timeout_seconds=${1:-180} retries=${2:-2}
	[[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ ]] || return 1
	[[ "${retries}" =~ ^[1-9][0-9]*$ ]] || return 1
	command -v timeout >/dev/null 2>&1 || return 1
}

hfl_docker_image_matches_platform() {
	local image=$1 platform="${2:-}" actual expected
	actual="$(docker image inspect "${image}" --format '{{.Os}}/{{.Architecture}}' 2>/dev/null || true)"
	[[ -n "${actual}" ]] || return 1
	[[ -z "${platform}" ]] && return 0
	case "${platform}" in
	*/*/*) expected="${platform%/*}" ;;
	*) expected="${platform}" ;;
	esac
	[[ "${actual}" == "${expected}" ]]
}

hfl_docker_pull_with_retry() {
	local image=$1 platform="${2:-}" timeout_seconds=${3:-180} retries=${4:-2}
	local attempt
	hfl_docker_validate_pull_settings "${timeout_seconds}" "${retries}" || {
		HFL_DOCKER_LAST_ERROR="invalid pull timeout/retry settings or timeout command unavailable"
		return 2
	}
	for attempt in $(seq 1 "${retries}"); do
		local -a args=(docker pull)
		[[ -n "${platform}" ]] && args+=(--platform "${platform}")
		args+=("${image}")
		if timeout --foreground "${timeout_seconds}s" "${args[@]}"; then
			return 0
		fi
		HFL_DOCKER_LAST_ERROR="pull ${image} failed (attempt ${attempt}/${retries})"
	done
	return 1
}

hfl_docker_ensure_image() {
	local image=$1 mirror="${2:-}" force_pull=${3:-0} offline=${4:-0}
	local platform="${5:-}" timeout_seconds=${6:-180} retries=${7:-2}
	local mirror_host mirrored=""
	HFL_DOCKER_IMAGE_SOURCE=""
	HFL_DOCKER_LAST_ERROR=""

	mirror_host="$(hfl_docker_normalize_mirror_host "${mirror}")"
	[[ -z "${mirror_host}" ]] || mirrored="$(hfl_docker_mirror_image_ref "${image}" "${mirror_host}")"

	if [[ "${force_pull}" -eq 0 ]] && hfl_docker_image_matches_platform "${image}" "${platform}"; then
		HFL_DOCKER_IMAGE_SOURCE="local"
		return 0
	fi
	if [[ "${force_pull}" -eq 0 && -n "${mirrored}" ]] \
		&& hfl_docker_image_matches_platform "${mirrored}" "${platform}"; then
		docker tag "${mirrored}" "${image}"
		HFL_DOCKER_IMAGE_SOURCE="local-mirror"
		return 0
	fi

	if [[ "${offline}" -eq 1 ]]; then
		if hfl_docker_image_matches_platform "${image}" "${platform}"; then
			HFL_DOCKER_IMAGE_SOURCE="local-offline"
			return 0
		fi
		if [[ -n "${mirrored}" ]] && hfl_docker_image_matches_platform "${mirrored}" "${platform}"; then
			docker tag "${mirrored}" "${image}"
			HFL_DOCKER_IMAGE_SOURCE="local-mirror-offline"
			return 0
		fi
		HFL_DOCKER_LAST_ERROR="${image} is missing and offline mode forbids registry access"
		return 1
	fi

	if [[ -n "${mirrored}" ]] \
		&& hfl_docker_pull_with_retry "${mirrored}" "${platform}" "${timeout_seconds}" "${retries}"; then
		docker tag "${mirrored}" "${image}"
		HFL_DOCKER_IMAGE_SOURCE="mirror"
		return 0
	fi
	if hfl_docker_pull_with_retry "${image}" "${platform}" "${timeout_seconds}" "${retries}"; then
		HFL_DOCKER_IMAGE_SOURCE="official"
		return 0
	fi

	if hfl_docker_image_matches_platform "${image}" "${platform}"; then
		HFL_DOCKER_IMAGE_SOURCE="local-fallback"
		return 0
	fi
	if [[ -n "${mirrored}" ]] && hfl_docker_image_matches_platform "${mirrored}" "${platform}"; then
		docker tag "${mirrored}" "${image}"
		HFL_DOCKER_IMAGE_SOURCE="local-mirror-fallback"
		return 0
	fi
	HFL_DOCKER_LAST_ERROR="unable to resolve ${image} from local cache, mirror, or official registry"
	return 1
}
