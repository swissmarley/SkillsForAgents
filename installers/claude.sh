#!/usr/bin/env bash
# Claude Code adapter.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

CLAUDE_ROOT="${CLAUDE_HOME:-$HOME/.claude}"
AGENT_SKILLS_DIR="$CLAUDE_ROOT/skills"
AGENT_COMMANDS_DIR="$CLAUDE_ROOT/commands"
AGENT_CLAUDE_MD="$CLAUDE_ROOT/CLAUDE.md"

mkdir -p "$AGENT_SKILLS_DIR" "$AGENT_COMMANDS_DIR"

while IFS= read -r name; do
  [[ -n "$name" ]] && install_one_skill "$name"
done <<<"$SFA_TARGETS"

if [[ "$SFA_UNINSTALL" == "1" ]]; then
  remove_triggers_block "$AGENT_CLAUDE_MD"
else
  write_triggers_block "$AGENT_CLAUDE_MD"
  ok "Tip: in Claude Code you can ALSO browse this repo as a plugin marketplace:"
  echo "    /plugin marketplace add swissmarley/SkillsForAgents"
fi
