#!/usr/bin/env bash
# SkillsForAgents — one-line installer
#
# Quick usage (from a clone):
#   ./install.sh --agent claude
#
# Quick usage (curl-pipe):
#   curl -fsSL https://raw.githubusercontent.com/<owner>/SkillsForAgents/main/install.sh | bash -s -- --agent claude
#
# Flags:
#   --agent <claude|codex|opencode|hermes>   Target agent (required, or set $SFA_AGENT)
#   --only <a,b,c>                           Install only these skills (comma-separated)
#   --exclude <a,b,c>                        Install everything except these
#   --mode <symlink|copy>                    Default: symlink
#   --ref <branch|tag|sha>                   When curl-piped, which git ref to fetch (default: main)
#   --repo <owner/name>                      Override repo (default: swissmarley/SkillsForAgents)
#   --brain <path>                           Pre-set $OBSIDIAN_BRAIN_PATH (skip prompt)
#   --no-claude-md                           Skip registering trigger phrases in CLAUDE.md
#   --no-venv                                Skip Python venv setup
#   --uninstall                              Remove previously installed skills
#   -y / --yes                               Non-interactive (assume defaults for prompts)
#   -h / --help                              Show this help
set -euo pipefail

REPO_DEFAULT="swissmarley/SkillsForAgents"
REF_DEFAULT="main"

AGENT="${SFA_AGENT:-}"
ONLY=""
EXCLUDE=""
MODE="symlink"
REF="$REF_DEFAULT"
REPO="$REPO_DEFAULT"
BRAIN=""
SKIP_CLAUDE_MD=0
SKIP_VENV=0
UNINSTALL=0
ASSUME_YES=0

print_help() {
  sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)        AGENT="$2"; shift 2 ;;
    --only)         ONLY="$2"; shift 2 ;;
    --exclude)      EXCLUDE="$2"; shift 2 ;;
    --mode)         MODE="$2"; shift 2 ;;
    --ref)          REF="$2"; shift 2 ;;
    --repo)         REPO="$2"; shift 2 ;;
    --brain)        BRAIN="$2"; shift 2 ;;
    --no-claude-md) SKIP_CLAUDE_MD=1; shift ;;
    --no-venv)      SKIP_VENV=1; shift ;;
    --uninstall)    UNINSTALL=1; shift ;;
    -y|--yes)       ASSUME_YES=1; shift ;;
    -h|--help)      print_help; exit 0 ;;
    *)              echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

c_reset='\033[0m'; c_bold='\033[1m'
c_green='\033[32m'; c_yellow='\033[33m'; c_red='\033[31m'; c_cyan='\033[36m'
log()  { printf "${c_cyan}▸${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}✓${c_reset} %s\n" "$*"; }
warn() { printf "${c_yellow}⚠${c_reset} %s\n" "$*"; }
die()  { printf "${c_red}✗${c_reset} %s\n" "$*" >&2; exit 1; }
ask()  {
  local q="$1" def="${2:-}" ans
  if [[ $ASSUME_YES -eq 1 ]]; then printf '%s\n' "$def"; return; fi
  if [[ -n "$def" ]]; then read -r -p "$q [$def]: " ans </dev/tty || true; printf '%s\n' "${ans:-$def}"
  else read -r -p "$q: " ans </dev/tty || true; printf '%s\n' "$ans"
  fi
}

# --- 0. Resolve repo root: local checkout or fetch via curl/git ----------------

SCRIPT_DIR=""
if _d="$(dirname -- "${BASH_SOURCE[0]:-$0}" 2>/dev/null)" && _abs="$(cd -- "$_d" 2>/dev/null && pwd)"; then
  SCRIPT_DIR="$_abs"
fi
unset _d _abs
if [[ -n "${SCRIPT_DIR:-}" && -f "$SCRIPT_DIR/skills.json" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
  log "Using local checkout at $REPO_ROOT"
else
  TMP_ROOT="$(mktemp -d -t sfa-XXXXXX)"
  trap 'rm -rf "$TMP_ROOT"' EXIT
  log "Fetching $REPO@$REF into $TMP_ROOT"
  if command -v git >/dev/null 2>&1; then
    git clone --depth 1 --branch "$REF" "https://github.com/$REPO.git" "$TMP_ROOT/repo" >/dev/null 2>&1 \
      || git clone --depth 1 "https://github.com/$REPO.git" "$TMP_ROOT/repo" >/dev/null 2>&1 \
      || die "git clone failed"
  else
    command -v curl >/dev/null 2>&1 || die "Need curl or git installed"
    mkdir -p "$TMP_ROOT/repo"
    curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$REF" \
      | tar -xz --strip-components=1 -C "$TMP_ROOT/repo" \
      || die "Tarball fetch failed"
  fi
  REPO_ROOT="$TMP_ROOT/repo"
fi

# --- 1. Agent + adapter --------------------------------------------------------

if [[ -z "$AGENT" ]]; then
  echo
  echo "Pick a target agent:"
  echo "  1) claude     — Claude Code (~/.claude/)"
  echo "  2) codex      — Codex CLI (~/.codex/)"
  echo "  3) opencode   — OpenCode (~/.config/opencode/)"
  echo "  4) hermes     — Hermes (~/.config/hermes/)"
  pick="$(ask 'Number' '1')"
  case "$pick" in
    1) AGENT=claude ;;
    2) AGENT=codex ;;
    3) AGENT=opencode ;;
    4) AGENT=hermes ;;
    *) die "Invalid choice" ;;
  esac
fi

ADAPTER="$REPO_ROOT/installers/$AGENT.sh"
[[ -f "$ADAPTER" ]] || die "No installer for agent '$AGENT' (looked at $ADAPTER)"

# --- 2. Parse skills.yaml ------------------------------------------------------

MANIFEST="$REPO_ROOT/skills.json"
[[ -f "$MANIFEST" ]] || die "skills.json not found at $MANIFEST"
command -v python3 >/dev/null 2>&1 || die "python3 is required (only for parsing skills.json)"

ALL_SKILLS="$(python3 - "$MANIFEST" <<'PY'
import sys, json
data = json.load(open(sys.argv[1]))
for s in data.get("skills", []):
    print(s["name"])
PY
)" || die "Failed to read skills.json"

FILTER_LIST() {
  local input="$1" only="$2" exclude="$3"
  while read -r name; do
    [[ -z "$name" ]] && continue
    if [[ -n "$only" ]] && ! echo ",$only," | grep -q ",$name,"; then continue; fi
    if [[ -n "$exclude" ]] && echo ",$exclude," | grep -q ",$name,"; then continue; fi
    echo "$name"
  done <<<"$input"
}

TARGETS="$(FILTER_LIST "$ALL_SKILLS" "$ONLY" "$EXCLUDE")"
[[ -n "$TARGETS" ]] || die "No skills selected"

log "Installing skills for agent: ${c_bold}$AGENT${c_reset}"
log "Mode: $MODE"
log "Skills: $(echo "$TARGETS" | tr '\n' ' ')"

# --- 3. Brain path config (shared) ---------------------------------------------

NEEDS_BRAIN=0
for s in $TARGETS; do
  case "$s" in session-journal|wiki-save|magic-content) NEEDS_BRAIN=1 ;; esac
done

if [[ $NEEDS_BRAIN -eq 1 && $UNINSTALL -eq 0 ]]; then
  if [[ -z "$BRAIN" && -z "${OBSIDIAN_BRAIN_PATH:-}" ]]; then
    BRAIN="$(ask 'Path to your Obsidian-style brain/wiki' "$HOME/Documents/Obsidian/Brain")"
  fi
  BRAIN="${BRAIN:-${OBSIDIAN_BRAIN_PATH:-$HOME/Documents/Obsidian/Brain}}"
  BRAIN="${BRAIN/#\~/$HOME}"
  mkdir -p "$HOME/.config/skills-for-agents"
  printf '%s\n' "$BRAIN" > "$HOME/.config/skills-for-agents/brain-path"
  ok "Brain path saved: $BRAIN"
fi

# --- 4. Hand off to the per-agent adapter --------------------------------------

export SFA_REPO_ROOT="$REPO_ROOT"
export SFA_TARGETS="$TARGETS"
export SFA_MODE="$MODE"
export SFA_SKIP_CLAUDE_MD="$SKIP_CLAUDE_MD"
export SFA_SKIP_VENV="$SKIP_VENV"
export SFA_UNINSTALL="$UNINSTALL"
export SFA_ASSUME_YES="$ASSUME_YES"

# shellcheck disable=SC1090
bash "$ADAPTER"

echo
if [[ $UNINSTALL -eq 1 ]]; then
  ok "Uninstall complete."
else
  ok "Done. Restart your agent so it picks up new skills and CLAUDE.md changes."
fi
