#!/bin/bash
set -e

# When run via r.sh, /app is a bind-mount of host static/js (including node_modules).
# Prefer reusing that tree; only fetch packages that are missing or out of date.

if [ -d "node_modules" ] && [ -f "node_modules/.package-lock.json" ]; then
  echo "Reusing existing node_modules (skip full reinstall)..."
  # prefer-offline: use local packages first; only hit the registry for gaps
  npm install --production=false --prefer-offline --no-audit --no-fund
else
  echo "Installing dependencies (no usable node_modules found)..."
  npm install --production=false --no-audit --no-fund
fi

echo "Building production bundle..."
npm run build

echo "Build completed successfully!"
