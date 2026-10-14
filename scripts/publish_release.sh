#!/usr/bin/env bash
set -euo pipefail

: "${TAG_NAME:?TAG_NAME is required}"
assets_dir="${1:-release-assets}"
if [[ ! -d "$assets_dir" || -L "$assets_dir" ]]; then
  printf 'Release assets directory is missing or invalid: %s\n' "$assets_dir" >&2
  exit 1
fi

mapfile -d '' windows_executables < <(
  find "$assets_dir" -mindepth 1 -maxdepth 1 -type f -iname '*.exe' -print0
)
if [[ ${#windows_executables[@]} -ne 1 ]]; then
  printf 'Expected exactly one Windows EXE, found %s.\n' "${#windows_executables[@]}" >&2
  exit 1
fi
windows_exe="${windows_executables[0]}"
windows_exe_name="${windows_exe##*/}"
if [[ ! "$windows_exe_name" =~ ^smn-.+-[0-9a-f]{7,}\.exe$ ]]; then
  printf 'Unexpected Windows EXE name: %s\n' "$windows_exe_name" >&2
  exit 1
fi
if (( ${#windows_exe_name} > 28 )); then
  printf 'Windows EXE name exceeds 28 characters: %s\n' "$windows_exe_name" >&2
  exit 1
fi

asset_names=(
  "$windows_exe_name"
  send-minecraft-notifications-windows-x64.zip
  SHA256SUMS-windows-x64.txt
  send-minecraft-notifications-linux-x64
  send-minecraft-notifications-linux-x64.zip
  SHA256SUMS-linux-x64.txt
)
assets=()
for name in "${asset_names[@]}"; do
  test -s "$assets_dir/$name"
  assets+=("$assets_dir/$name")
done

expected_assets=()
for name in "${asset_names[@]}"; do
  expected_assets+=("$name")
done
shopt -s dotglob nullglob
entries=("$assets_dir"/*)
if [[ ${#entries[@]} -ne ${#asset_names[@]} ]]; then
  printf 'Unexpected asset count: expected %s files, found %s.\n' \
    "${#asset_names[@]}" "${#entries[@]}" >&2
  exit 1
fi
for entry in "${entries[@]}"; do
  name="${entry##*/}"
  is_expected=false
  for expected_name in "${expected_assets[@]}"; do
    if [[ "$name" == "$expected_name" ]]; then
      is_expected=true
      break
    fi
  done
  if [[ ! -f "$entry" || -L "$entry" || "$is_expected" != true ]]; then
    printf 'Unexpected release asset: %s\n' "$name" >&2
    exit 1
  fi
done
(
  cd "$assets_dir"
  sha256sum --check SHA256SUMS-windows-x64.txt
  sha256sum --check SHA256SUMS-linux-x64.txt
)

prerelease=false
if [[ "$TAG_NAME" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+- ]]; then
  prerelease=true
fi

if is_draft=$(gh release view "$TAG_NAME" --json isDraft --jq '.isDraft' 2>/dev/null); then
  if [[ "$is_draft" == false ]]; then
    printf 'Release %s is already published; keeping its existing assets.\n' "$TAG_NAME"
    exit 0
  fi
  test "$is_draft" = true
  gh release upload "$TAG_NAME" "${assets[@]}" --clobber
else
  # Keep incomplete uploads in a draft until every asset has been attached.
  gh release create "$TAG_NAME" "${assets[@]}" --verify-tag --draft --title "$TAG_NAME" --generate-notes
fi
gh release edit "$TAG_NAME" --draft=false --prerelease="$prerelease"
