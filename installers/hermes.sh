#!/usr/bin/env bash
# Hermes adapter (placeholder layout — confirm with your Hermes install).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

H_ROOT="${HERMES_HOME:-$HOME/.config/hermes}"
AGENT_SKILLS_DIR="$H_ROOT/skills"
AGENT_COMMANDS_DIR="$H_ROOT/commands"
AGENT_CLAUDE_MD="$H_ROOT/AGENTS.md"

mkdir -p "$AGENT_SKILLS_DIR" "$AGENT_COMMANDS_DIR"

while IFS= read -r name; do
  [[ -n "$name" ]] && install_one_skill "$name"
done <<<"$SFA_TARGETS"

if [[ "$SFA_UNINSTALL" == "1" ]]; then
  remove_triggers_block "$AGENT_CLAUDE_MD"
else
  write_triggers_block "$AGENT_CLAUDE_MD"
fi
