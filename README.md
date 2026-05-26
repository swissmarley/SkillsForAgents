# SkillsForAgents

A growing marketplace of **agent skills** that drop into Claude Code, Codex CLI, OpenCode, and Hermes with a single command. Each skill is a self-contained folder with a `SKILL.md` (Anthropic-style), optional slash commands, scripts, and assets.

```bash
# One-liner — installs everything for Claude Code
curl -fsSL https://raw.githubusercontent.com/swissmarley/SkillsForAgents/main/install.sh \
  | bash -s -- --agent claude
```

Or, in Claude Code, browse this repo as a plugin marketplace:

```text
/plugin marketplace add swissmarley/SkillsForAgents
```

---

## What's inside

| Skill | What it does | Triggers |
|---|---|---|
| **session-journal** | Records work sessions into an Obsidian-style brain/wiki and archives them on demand. | "Hey Claude, let's go!" → "I'm done for today" |
| **wiki-save** | Saves the current idea/snippet into your wiki under concepts / entities / synthesis / reflections. | "save this", "save to wiki", `/save` |
| **magic-content** | Interactive research pipeline: YouTube/Web/PDF discovery → NotebookLM artifacts → wiki ingest. | `/magic-content`, `MAGIC <topic>` |
| **magic-web** | Immersive scroll-driven hero website factory: topic → 4 prompts → 2 frames (Nano Banana 2/Pro) → 8 s 1080p video (Veo 3.1 Fast/Lite) → 1920×1004 frames → Antigravity website. 100% Gemini API; choose AI Studio key or Vertex AI; cost preview up front. | `/magic-web`, "POWER HERO" |
| **vapi-build** | End-to-end builder for production Vapi voice agents with custom n8n tools. | `/vapi-build`, "VAPI GO" |

---

## Install

The installer always sets up **everything** the skill needs to work on first run: it copies (or symlinks) the skill files to the agent's skill directory, places slash commands, registers trigger phrases in your `CLAUDE.md` / `AGENTS.md`, creates a Python `.venv` for skills that ship `requirements.txt`, and saves the `OBSIDIAN_BRAIN_PATH` config for skills that read/write notes.

### Quickstart

```bash
# Install everything for Claude Code (symlinks, so `git pull` updates live)
curl -fsSL https://raw.githubusercontent.com/swissmarley/SkillsForAgents/main/install.sh \
  | bash -s -- --agent claude

# Or clone first, then install (recommended for development)
git clone https://github.com/swissmarley/SkillsForAgents
cd SkillsForAgents
./install.sh --agent claude
```

### Pick your agent

| Agent | Flag | Installs to |
|---|---|---|
| Claude Code | `--agent claude` | `~/.claude/skills/`, `~/.claude/commands/`, `~/.claude/CLAUDE.md` |
| Codex CLI | `--agent codex` | `~/.codex/skills/`, `~/.codex/commands/`, `~/.codex/AGENTS.md` |
| OpenCode | `--agent opencode` | `~/.config/opencode/skills/`, `~/.config/opencode/command/`, `~/.config/opencode/AGENTS.md` |
| Hermes | `--agent hermes` | `~/.config/hermes/skills/`, `~/.config/hermes/commands/`, `~/.config/hermes/AGENTS.md` |

### Useful flags

```text
--only a,b,c        Install only these skills
--exclude a,b,c     Install everything except these
--mode symlink|copy Default: symlink (git pull = updates live)
--brain <path>      Pre-set $OBSIDIAN_BRAIN_PATH (skip prompt)
--no-venv           Skip Python venv setup
--no-claude-md      Don't touch CLAUDE.md / AGENTS.md
--uninstall         Remove a previous install (clean)
-y, --yes           Non-interactive (assume defaults)
```

Examples:

```bash
# Just the research pipeline, for Codex, no venv
./install.sh --agent codex --only magic-content --no-venv

# Everything except the voice-agent builder, in copy mode
./install.sh --agent claude --exclude vapi-build --mode copy

# Clean uninstall
./install.sh --agent claude --uninstall

# Just the immersive-website builder
./install.sh --agent claude --only magic-web
```

---

## Configuration

Three skills (`session-journal`, `wiki-save`, `magic-content`) read/write into an Obsidian-style brain/wiki. The installer asks once at install time and writes the path to `~/.config/skills-for-agents/brain-path`. You can override per-shell with the `OBSIDIAN_BRAIN_PATH` env var.

Skills that need external CLIs:

- **magic-content** → [`notebooklm` CLI](https://github.com/) (run `notebooklm login` once)
- **magic-web** → `ffmpeg` (e.g. `brew install ffmpeg`), the Antigravity CLI, and `pip install google-genai`. Set **either** `GEMINI_API_KEY` (Google AI Studio) **or** `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` + `GOOGLE_APPLICATION_CREDENTIALS` (Vertex AI). The skill asks you to pick one auth path on first run and remembers it.
- **vapi-build** → [`vapi` CLI](https://docs.vapi.ai/cli) (run `vapi login` once) and optionally an n8n instance

---

## Adding your own skill

1. Drop a folder under `skills/<your-skill>/` with at least a `SKILL.md`.
2. Add an entry to `skills.json` (see [`docs/adding-a-skill.md`](docs/adding-a-skill.md)).
3. Open a PR — CI validates the schema and trigger registration.

---

## Why a marketplace?

Anthropic's Claude Code introduced a native plugin marketplace, and the broader agent ecosystem (Codex, OpenCode, Hermes) is converging on the same `SKILL.md` convention. This repo treats skills as portable artifacts: one source of truth (`skills.json`), four install paths, one curl one-liner.

## License

MIT — see [LICENSE](LICENSE).
