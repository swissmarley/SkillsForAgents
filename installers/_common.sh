#!/usr/bin/env bash
# Shared helpers for per-agent installers.
# Adapters source this file and expose: install_one_skill, register_triggers, write_command, etc.
#
# Inputs (exported by install.sh):
#   SFA_REPO_ROOT     repo root
#   SFA_TARGETS       newline-separated skill names
#   SFA_MODE          symlink | copy
#   SFA_SKIP_CLAUDE_MD 1 to skip CLAUDE.md trigger registration
#   SFA_SKIP_VENV     1 to skip venv setup
#   SFA_UNINSTALL     1 to remove instead of install
#   SFA_ASSUME_YES    1 to skip prompts
#
# Adapters must define:
#   AGENT_SKILLS_DIR     where SKILL.md folders live
#   AGENT_COMMANDS_DIR   where slash command .md files live (or "" if unsupported)
#   AGENT_CLAUDE_MD      path to the user's CLAUDE.md / AGENTS.md / equivalent (or "" if unsupported)

set -euo pipefail

c_reset='\033[0m'; c_green='\033[32m'; c_yellow='\033[33m'; c_red='\033[31m'; c_cyan='\033[36m'
log()  { printf "${c_cyan}▸${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}✓${c_reset} %s\n" "$*"; }
warn() { printf "${c_yellow}⚠${c_reset} %s\n" "$*"; }
die()  { printf "${c_red}✗${c_reset} %s\n" "$*" >&2; exit 1; }

# Read a per-skill field from skills.json using python.
skill_field() {
  local name="$1" field="$2"
  python3 - "$SFA_REPO_ROOT/skills.json" "$name" "$field" <<'PY'
import sys, json
data = json.load(open(sys.argv[1]))
name, field = sys.argv[2], sys.argv[3]
for s in data.get("skills", []):
    if s["name"] == name:
        v = s.get(field, "")
        if isinstance(v, (list, dict)):
            print(json.dumps(v))
        else:
            print(v if v is not None else "")
        break
PY
}

place_skill() {
  local src="$1" dst="$2"
  if [[ -e "$dst" || -L "$dst" ]]; then
    rm -rf "$dst"
  fi
  mkdir -p "$(dirname "$dst")"
  case "$SFA_MODE" in
    symlink) ln -s "$src" "$dst" ;;
    copy)
      cp -R "$src" "$dst"
      # Strip macOS metadata that hitches a ride on copies
      find "$dst" \( -name '._*' -o -name '.DS_Store' \) -delete 2>/dev/null || true
      ;;
    *)       die "Unknown mode: $SFA_MODE" ;;
  esac
}

place_command() {
  local src="$1" dst="$2"
  [[ -n "${AGENT_COMMANDS_DIR:-}" ]] || return 0
  [[ -f "$src" ]] || return 0
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" || -L "$dst" ]]; then rm -f "$dst"; fi
  case "$SFA_MODE" in
    symlink) ln -s "$src" "$dst" ;;
    copy)    cp "$src" "$dst" ;;
  esac
}

setup_python_venv() {
  local skill_dir="$1" req_rel="$2"
  [[ "$SFA_SKIP_VENV" == "1" ]] && return 0
  local req="$skill_dir/$req_rel"
  [[ -f "$req" ]] || return 0
  command -v python3 >/dev/null 2>&1 || { warn "python3 not found — skipping venv for $skill_dir"; return 0; }
  if [[ ! -d "$skill_dir/.venv" ]]; then
    log "Creating venv: $skill_dir/.venv"
    python3 -m venv "$skill_dir/.venv"
  fi
  log "Installing requirements: $req_rel"
  "$skill_dir/.venv/bin/pip" install --quiet --upgrade pip
  "$skill_dir/.venv/bin/pip" install --quiet -r "$req"
}

# Block markers in CLAUDE.md / AGENTS.md so we can update or remove cleanly.
SFA_BLOCK_BEGIN="<!-- BEGIN SkillsForAgents:auto-managed -->"
SFA_BLOCK_END="<!-- END SkillsForAgents:auto-managed -->"

write_triggers_block() {
  local target_file="$1"
  [[ "$SFA_SKIP_CLAUDE_MD" == "1" ]] && return 0
  [[ -n "$target_file" ]] || return 0
  mkdir -p "$(dirname "$target_file")"
  touch "$target_file"
  SFA_TARGET_FILE="$target_file" \
  SFA_BEGIN="$SFA_BLOCK_BEGIN" \
  SFA_END="$SFA_BLOCK_END" \
  python3 - "$SFA_REPO_ROOT/skills.json" <<'PY'
import os, re, sys, json
data = json.load(open(sys.argv[1]))
targets = set(os.environ.get("SFA_TARGETS", "").split())
target_file = os.environ["SFA_TARGET_FILE"]
begin = os.environ["SFA_BEGIN"]
end = os.environ["SFA_END"]

lines = [
    begin,
    "# SkillsForAgents — auto-managed trigger registry",
    "# Re-run the installer to refresh; do not edit between markers by hand.",
    "",
]
for s in data.get("skills", []):
    if s["name"] not in targets:
        continue
    lines.append(f"## {s['name']}")
    lines.append(f"- **{s['name']}** — {s['description']}")
    triggers = s.get("triggers") or []
    if triggers:
        phrases = ", ".join(f'"{t["phrase"]}"' for t in triggers)
        lines.append(
            f"  When the user says {phrases}, invoke the Skill tool with "
            f"`skill: \"{s['name']}\"` before doing anything else."
        )
    lines.append("")
lines.append(end)
block = "\n".join(lines)

text = open(target_file).read() if os.path.exists(target_file) else ""
pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
if pat.search(text):
    text = pat.sub(block, text)
else:
    text = (text.rstrip() + "\n\n" + block + "\n") if text.strip() else (block + "\n")
open(target_file, "w").write(text)
print(f"updated:{target_file}")
PY
  ok "Updated triggers in $target_file"
}

remove_triggers_block() {
  local target_file="$1"
  [[ -f "$target_file" ]] || return 0
  if grep -qF "$SFA_BLOCK_BEGIN" "$target_file"; then
    python3 - "$target_file" "$SFA_BLOCK_BEGIN" "$SFA_BLOCK_END" <<'PY'
import sys, re
path, begin, end = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()
pat = re.compile(r"\n*" + re.escape(begin) + r".*?" + re.escape(end) + r"\n*", re.DOTALL)
open(path,"w").write(pat.sub("\n", text))
PY
    ok "Removed trigger block from $target_file"
  fi
}

install_one_skill() {
  local name="$1"
  local src="$SFA_REPO_ROOT/skills/$name"
  local dst="$AGENT_SKILLS_DIR/$name"
  [[ -d "$src" ]] || die "Skill source missing: $src"

  if [[ "$SFA_UNINSTALL" == "1" ]]; then
    [[ -e "$dst" || -L "$dst" ]] && { rm -rf "$dst"; ok "Removed $dst"; }
    # Remove commands
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      local slash; slash="$(echo "$line" | python3 -c 'import json,sys; d=json.loads(sys.stdin.read() or "{}"); print(d.get("slash",""))' 2>/dev/null || true)"
      [[ -n "$slash" && -n "${AGENT_COMMANDS_DIR:-}" ]] && rm -f "$AGENT_COMMANDS_DIR/$slash.md"
    done < <(skill_field "$name" commands | python3 -c 'import json,sys; [print(json.dumps(c)) for c in json.loads(sys.stdin.read() or "[]")]' 2>/dev/null || true)
    return 0
  fi

  log "Installing skill: $name"
  place_skill "$src" "$dst"

  # Commands
  if [[ -n "${AGENT_COMMANDS_DIR:-}" ]]; then
    while IFS= read -r row; do
      [[ -z "$row" ]] && continue
      local file slash
      file="$(echo "$row" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["file"])')"
      slash="$(echo "$row" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["slash"])')"
      place_command "$src/$file" "$AGENT_COMMANDS_DIR/$slash.md"
    done < <(skill_field "$name" commands | python3 -c 'import json,sys,os; [print(json.dumps(c)) for c in (json.loads(sys.stdin.read() or "[]"))]' 2>/dev/null || true)
  fi

  # Requirements (Python)
  local req
  req="$(skill_field "$name" requirements | python3 -c 'import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get("python","") if isinstance(d,dict) else "")
except Exception: print("")' 2>/dev/null || true)"
  if [[ -n "$req" ]]; then setup_python_venv "$src" "$req"; fi

  ok "$name ready"
}
