#!/usr/bin/env bash
# validate-env.sh — Check that the current CUBRID worktree is ready for OOS development.
# Exits 0 if all checks pass, 1 if any fail. Prints warnings/errors to stderr.
# Usage: bash validate-env.sh [directory]
#   directory: path to check (defaults to $PWD)

set -euo pipefail

DIR="${1:-$PWD}"
ERRORS=0
WARNINGS=0

# Colors (disabled if not a terminal)
if [ -t 2 ]; then
  RED='\033[0;31m'; YELLOW='\033[0;33m'; GREEN='\033[0;32m'; BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; YELLOW=''; GREEN=''; BOLD=''; RESET=''
fi

ok()   { echo -e "${GREEN}[OK]${RESET}    $1" >&2; }
warn() { echo -e "${YELLOW}[WARN]${RESET}  $1" >&2; WARNINGS=$((WARNINGS + 1)); }
fail() { echo -e "${RED}[FAIL]${RESET}  $1" >&2; ERRORS=$((ERRORS + 1)); }
info() { echo -e "        $1" >&2; }

echo -e "${BOLD}=== CUBRID OOS Environment Validation ===${RESET}" >&2
echo -e "Checking: ${DIR}" >&2
echo "" >&2

# --- 1. Git repository or worktree ---
if git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1; then
  if git -C "$DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    branch=$(git -C "$DIR" branch --show-current 2>/dev/null || echo "(detached)")
    ok "Git repository (branch: $branch)"
  else
    fail "Inside .git directory, not a work tree"
  fi
else
  fail "Not a git repository — code search and git features won't work"
  info "Run from a CUBRID repo clone or worktree"
fi

# --- 2. CUBRID source tree ---
if [ -f "$DIR/CMakeLists.txt" ] && [ -f "$DIR/CMakePresets.json" ]; then
  ok "CUBRID source tree detected (CMakeLists.txt + CMakePresets.json)"
else
  fail "Not a CUBRID source tree — missing CMakeLists.txt or CMakePresets.json"
  info "Make sure you're in the root of a CUBRID checkout"
fi

# --- 3. OOS source files ---
oos_file=$(find "$DIR/src" -name "oos_file.cpp" -maxdepth 5 2>/dev/null | head -1)
if [ -n "$oos_file" ]; then
  ok "OOS source found: $(realpath --relative-to="$DIR" "$oos_file" 2>/dev/null || echo "$oos_file")"
else
  warn "oos_file.cpp not found — are you on the feat/oos branch?"
  info "OOS code lives on feat/oos or derived branches"
fi

# --- 4. PRESET_MODE environment variable ---
if [ -n "${PRESET_MODE:-}" ]; then
  ok "PRESET_MODE=$PRESET_MODE"
else
  warn "PRESET_MODE not set — build directory detection may fail"
  info "Source .envrc or set PRESET_MODE (e.g., release_gcc, debug_clang)"
  # Try to auto-detect from existing build directories
  detected=$(ls -d "$DIR"/build_preset_* 2>/dev/null | head -1 | sed 's|.*/build_preset_||')
  if [ -n "$detected" ]; then
    info "Auto-detected build preset: $detected"
    PRESET_MODE="$detected"
  fi
fi

# --- 5. Build directory ---
if [ -n "${PRESET_MODE:-}" ]; then
  BUILD_DIR="$DIR/build_preset_${PRESET_MODE}"
  if [ -d "$BUILD_DIR" ]; then
    ok "Build directory exists: build_preset_${PRESET_MODE}/"
  else
    fail "Build directory missing: build_preset_${PRESET_MODE}/"
    info "Run: just build   (or: cmake --preset ${PRESET_MODE})"
  fi
else
  # Check for any build directory
  any_build=$(ls -d "$DIR"/build_preset_* 2>/dev/null | head -1)
  if [ -n "$any_build" ]; then
    warn "Build directory found ($(basename "$any_build")) but PRESET_MODE not set"
    BUILD_DIR="$any_build"
  else
    fail "No build directory found (build_preset_*)"
    info "Run: just build"
  fi
fi

# --- 6. compile_commands.json ---
CCJ_ROOT="$DIR/compile_commands.json"
CCJ_BUILD="${BUILD_DIR:-$DIR/build_preset_unknown}/compile_commands.json"

if [ -f "$CCJ_ROOT" ] || [ -L "$CCJ_ROOT" ]; then
  if [ -L "$CCJ_ROOT" ]; then
    target=$(readlink "$CCJ_ROOT")
    if [ -f "$DIR/$target" ] || [ -f "$CCJ_ROOT" ]; then
      ok "compile_commands.json symlink at root -> $target"
    else
      fail "compile_commands.json symlink broken -> $target"
      info "Rebuild or run: ln -sf build_preset_\${PRESET_MODE}/compile_commands.json ."
    fi
  else
    ok "compile_commands.json exists at project root"
  fi
elif [ -f "$CCJ_BUILD" ]; then
  warn "compile_commands.json found in build dir but not symlinked to root"
  info "LSP may not find it. Run: ln -sf build_preset_\${PRESET_MODE}/compile_commands.json ."
else
  fail "compile_commands.json not found — LSP features (hover, references, goto-def) won't work"
  info "Build with: just build   (CMake generates it with CMAKE_EXPORT_COMPILE_COMMANDS=ON)"
fi

# --- 7. clangd availability ---
if command -v clangd >/dev/null 2>&1; then
  clangd_ver=$(clangd --version 2>/dev/null | head -1)
  ok "clangd available: $clangd_ver"
else
  warn "clangd not found — LSP hover/references/goto-def won't work"
  info "Install clangd (e.g., sudo dnf install clang-tools-extra)"
fi

# --- 8. just command ---
if command -v just >/dev/null 2>&1; then
  ok "just available"
else
  warn "just not found — build shortcuts (just build, just ctest) unavailable"
  info "Install: cargo install just"
fi

# --- Summary ---
echo "" >&2
if [ "$ERRORS" -gt 0 ]; then
  echo -e "${RED}${BOLD}$ERRORS error(s), $WARNINGS warning(s)${RESET} — environment not ready" >&2
  echo -e "Fix the errors above before proceeding with OOS development." >&2
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  echo -e "${YELLOW}${BOLD}$WARNINGS warning(s)${RESET} — environment partially ready" >&2
  echo -e "OOS context loading will proceed, but some features may be limited." >&2
  exit 0
else
  echo -e "${GREEN}${BOLD}All checks passed${RESET} — environment ready for OOS development" >&2
  exit 0
fi
