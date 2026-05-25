#!/usr/bin/env bash
# OpenCode adapter.
# OpenCode reads from ~/.config/opencode/. Skill convention is evolving; we install
# under skills/ and register triggers in AGENTS.md so the rules apply globally.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

OC_ROOT="${OPENCODE_HOME:-$HOME/.config/opencode}"
AGENT_SKILLS_DIR="$OC_ROOT/skills"
AGENT_COMMANDS_DIR="$OC_ROOT/command"   # OpenCode uses singular "command"
AGENT_CLAUDE_MD="$OC_ROOT/AGENTS.md"

mkdir -p "$AGENT_SKILLS_DIR" "$AGENT_COMMANDS_DIR"

while IFS= read -r name; do
  [[ -n "$name" ]] && install_one_skill "$name"
done <<<"$SFA_TARGETS"

if [[ "$SFA_UNINSTALL" == "1" ]]; then
  remove_triggers_block "$AGENT_CLAUDE_MD"
else
  write_triggers_block "$AGENT_CLAUDE_MD"
fi
