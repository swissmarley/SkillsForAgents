# Provider notes

Each agent has its own install layout. The installer hides the differences, but if you're debugging or installing manually, here's where things land.

## Claude Code

| | Path |
|---|---|
| Skills | `~/.claude/skills/<name>/` |
| Commands | `~/.claude/commands/<slash>.md` |
| Global instructions | `~/.claude/CLAUDE.md` |
| Plugin marketplace | `/plugin marketplace add swissmarley/SkillsForAgents` |

The marketplace path is fully native: `.claude-plugin/marketplace.json` declares each skill as a plugin, so users can browse and toggle skills individually via the `/plugin` UI without running our installer at all.

## Codex CLI

| | Path |
|---|---|
| Skills | `~/.codex/skills/<name>/` |
| Commands | `~/.codex/commands/<slash>.md` |
| Global instructions | `~/.codex/AGENTS.md` |

Codex's skill loader is newer than Claude Code's. If your install uses a different layout, set `CODEX_HOME` before running the installer.

## OpenCode

| | Path |
|---|---|
| Skills | `~/.config/opencode/skills/<name>/` |
| Commands | `~/.config/opencode/command/<slash>.md` (note: singular `command`) |
| Global instructions | `~/.config/opencode/AGENTS.md` |

## Hermes

| | Path |
|---|---|
| Skills | `~/.config/hermes/skills/<name>/` |
| Commands | `~/.config/hermes/commands/<slash>.md` |
| Global instructions | `~/.config/hermes/AGENTS.md` |

This is a best-guess layout. Override with `HERMES_HOME` if needed.

---

## Shared install behaviour

Across all providers, the installer:

1. **Places** each selected skill folder at `<root>/skills/<name>` (symlink by default, `--mode copy` to detach).
2. **Wires** each declared slash command into `<root>/<commands-dir>/<slash>.md`.
3. **Sets up** a Python `.venv` inside the skill folder for any skill that ships `requirements.txt`.
4. **Updates** the auto-managed trigger block in `<root>/<CLAUDE.md or AGENTS.md>` so the agent knows when to invoke each skill.
5. **Saves** shared config (e.g. `OBSIDIAN_BRAIN_PATH`) into `~/.config/skills-for-agents/` so every skill reads from the same place.

Running `--uninstall` reverses all five.
