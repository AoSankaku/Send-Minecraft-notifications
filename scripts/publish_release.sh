#!/usr/bin/env bash
set -euo pipefail

: "${TAG_NAME:?TAG_NAME is required}"
assets_dir="${1:-release-assets}"
asset_names=(
  send-minecraft-notifications-windows-x64.exe
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
