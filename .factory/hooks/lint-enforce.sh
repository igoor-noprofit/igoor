#!/usr/bin/env bash
# .factory/hooks/lint-enforce (no .sh extension recommended for cross-platform)
# Works on macOS/Linux; falls back gracefully on Windows (assumes Git Bash/MSYS2 or WSL)

set -euo pipefail

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

if [[ -z "$file_path" || ! -f "$file_path" ]]; then
  exit 0
fi

# Detect OS for tool paths / commands
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  # Windows (Git Bash, MSYS2, etc.)
  ESLINT="npx.cmd eslint"
  RUFF="ruff.exe"
  BLACK="black.exe"
  # Add .exe if tools are in PATH without it, or use full paths
else
  ESLINT="npx eslint"
  RUFF="ruff"
  BLACK="black"
fi

# JS/TS
if [[ "$file_path" =~ \.(js|jsx|ts|tsx|mjs|cjs)$ ]]; then
  if command -v npx >/dev/null && [ -f .eslintrc* -o -f eslint.config.js ]; then
    if ! $ESLINT --quiet "$file_path"; then
      echo "ESLint errors in $file_path — fix required." >&2
      $ESLINT --fix "$file_path" >/dev/null 2>&1 || true
      if ! $ESLINT --quiet "$file_path"; then
        echo "ESLint still fails after --fix on $file_path." >&2
        exit 2
      fi
    fi
  fi
fi

# Python
if [[ "$file_path" =~ \.py$ ]]; then
  if command -v ruff >/dev/null && [ -f pyproject.toml -o -f ruff.toml ]; then
    if ! $RUFF check --quiet "$file_path"; then
      echo "Ruff found issues in $file_path." >&2
      $RUFF check --fix --quiet "$file_path" >/dev/null 2>&1 || true
      if ! $RUFF check --quiet "$file_path"; then
        echo "Ruff still fails after auto-fix on $file_path." >&2
        exit 2
      fi
    fi
  fi
  # Black check (optional, warning-only)
  if command -v black >/dev/null; then
    $BLACK --check --quiet "$file_path" || echo "Black formatting needed in $file_path (warning)." >&2
  fi
fi

exit 0