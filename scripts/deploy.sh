#!/usr/bin/env bash
# One-shot deploy script for xiangmushu frontend.
#
# This script exists because the server runs 宝塔 (BT Panel) nginx,
# and the static files are served from /www/wwwroot/xiangmushu/ —
# NOT from /root/h/xiangmushu/frontend/dist/ where git/npm write.
#
# Usage (as root, from project root):
#   bash scripts/deploy.sh
#
# What it does:
#   1. git pull origin master
#   2. cd frontend && npm run build
#   3. rsync (or cp -r) dist/ contents to /www/wwwroot/xiangmushu/
#   4. Verify the new build hash appears in the copied index.html
#   5. Reload nginx if needed
#
# Exit codes:
#   0 success
#   1 git pull failed
#   2 npm build failed
#   3 copy/deploy failed
#   4 new hash not observed in target directory
#   5 nginx reload failed

set -euo pipefail

REPO_ROOT="/root/h/xiangmushu"
NGINX_ROOT="/www/wwwroot/xiangmushu"
NGINX_BIN="/www/server/nginx/sbin/nginx"

log() { printf '\033[1;36m▶\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m✗\033[0m %s\n' "$*" 1>&2; }

# ── 0. Preflight ──────────────────────────────────────────────
log "Preflight checks"
if [ ! -d "$REPO_ROOT/.git" ]; then
  err "Not a git repo: $REPO_ROOT"
  exit 1
fi
mkdir -p "$NGINX_ROOT"

# ── 1. Capture old build hash for comparison ──────────────────
OLD_HASH=""
if [ -f "$NGINX_ROOT/index.html" ]; then
  OLD_HASH=$(grep -oE "index-[A-Za-z0-9_-]{8}" "$NGINX_ROOT/index.html" | sort -u | tr '\n' ',' | sed 's/,$//')
  log "Current production hash: ${OLD_HASH:-<none>}"
fi

# ── 2. git pull ───────────────────────────────────────────────
log "git pull origin master"
cd "$REPO_ROOT"
if ! git pull origin master; then
  err "git pull failed"
  exit 1
fi
NEW_COMMIT=$(git rev-parse --short HEAD)
ok "HEAD is now $NEW_COMMIT"

# ── 3. npm run build ──────────────────────────────────────────
log "npm run build"
cd "$REPO_ROOT/frontend"
if ! npm run build; then
  err "npm build failed"
  exit 2
fi
NEW_DIST_HASH=$(grep -oE "index-[A-Za-z0-9_-]{8}" dist/index.html | head -1)
if [ -z "$NEW_DIST_HASH" ]; then
  err "Cannot read new hash from dist/index.html"
  exit 2
fi
ok "New build hash: $NEW_DIST_HASH"

# ── 4. Deploy to nginx root ──────────────────────────────────
log "Deploy to $NGINX_ROOT"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete dist/ "$NGINX_ROOT/"
else
  # Fallback: rm + cp
  rm -rf "${NGINX_ROOT:?}"/*
  cp -r dist/* "$NGINX_ROOT/"
fi
ok "Files copied"

# ── 5. Verify ────────────────────────────────────────────────
log "Verify new hash visible in nginx root"
DEPLOYED_HASH=$(grep -oE "index-[A-Za-z0-9_-]{8}" "$NGINX_ROOT/index.html" | head -1)
if [ "$DEPLOYED_HASH" != "$NEW_DIST_HASH" ]; then
  err "Deployed hash ($DEPLOYED_HASH) ≠ built hash ($NEW_DIST_HASH)"
  exit 4
fi
ok "Hash verified: $DEPLOYED_HASH"

# ── 6. Reload nginx if listening on 80 ───────────────────────
if ss -tlnp 2>/dev/null | grep -q ':80 '; then
  log "nginx is up — reloading"
  if [ -x "$NGINX_BIN" ]; then
    if "$NGINX_BIN" -s reload 2>/dev/null; then
      ok "nginx reloaded"
    else
      err "nginx reload failed (continuing anyway)"
    fi
  fi
else
  log "nginx not listening on :80 — skipping reload"
fi

# ── 7. Summary ───────────────────────────────────────────────
printf '\n\033[1;32m════════════════════════════════════════\033[0m\n'
printf '  %s  Deployed\n' "$(printf '\033[1m')$(printf '\033[0m')"
printf '  old hash: %s\n' "${OLD_HASH:-<none>}"
printf '  new hash: %s\n' "$NEW_DIST_HASH"
printf '  commit:   %s\n' "$NEW_COMMIT"
printf '\033[1;32m════════════════════════════════════════\033[0m\n'
printf '\nNext step: verify in browser with\n  node scripts/verify-after-deploy.cjs\n'
