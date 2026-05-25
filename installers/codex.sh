#!/usr/bin/env bash
# Codex CLI adapter.
# Codex uses AGENTS.md at the project root (or ~/.codex/AGENTS.md globally) and
# supports a `skills/` convention. Adjust the paths below if your Codex install
# uses a different layout.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
AGENT_SKILLS_DIR="$CODEX_ROOT/skills"
AGENT_COMMANDS_DIR="$CODEX_ROOT/commands"
AGENT_CLAUDE_MD="$CODEX_ROOT/AGENTS.md"

mkdir -p "$AGENT_SKILLS_DIR" "$AGENT_COMMANDS_DIR"

while IFS= read -r name; do
  [[ -n "$name" ]] && install_one_skill "$name"
done <<<"$SFA_TARGETS"

if [[ "$SFA_UNINSTALL" == "1" ]]; then
  remove_triggers_block "$AGENT_CLAUDE_MD"
else
  write_triggers_block "$AGENT_CLAUDE_MD"
fi
