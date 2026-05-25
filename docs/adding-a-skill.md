# Adding a skill

A skill is a folder under `skills/<name>/` plus one entry in `skills.json`. That's it — the installer reads `skills.json`, picks up new entries automatically, and CI validates the structure.

## Anatomy of a skill folder

```
skills/<name>/
├── SKILL.md              # required — Anthropic-style frontmatter + body
├── commands/             # optional — slash command files (.md)
│   └── <slash>.md
├── scripts/              # optional — code the skill calls (any language)
├── assets/               # optional — templates, JSON skeletons, etc.
├── references/           # optional — long-form reference docs the skill reads
├── requirements.txt      # optional — Python deps; triggers venv setup
└── tests/                # optional — recommend pytest for Python skills
```

## SKILL.md frontmatter

```yaml
---
name: <kebab-case-name>           # required — must match the folder name
description: <one paragraph>      # required — triggers and what the skill does
type: flexible                    # optional — flexible|rigid (Anthropic convention)
---
```

The body is plain Markdown. Keep instructions for the agent in the imperative ("Read X", "Ask Y", "Write Z"). Don't bury the trigger phrases — restate them in the body so the agent knows when to engage.

## skills.json entry

Add an object to the `skills` array:

```json
{
  "name": "<kebab-case-name>",
  "version": "1.0.0",
  "description": "<one sentence>",
  "tags": ["category", "topic"],
  "triggers": [
    { "phrase": "<exact phrase>", "kind": "activation" }
  ],
  "commands": [
    { "file": "commands/<slash>.md", "slash": "<slash>" }
  ],
  "requirements": { "python": "requirements.txt" },
  "env": ["OPTIONAL_ENV_VAR_THE_SKILL_READS"],
  "external_tools": [
    { "name": "some-cli", "description": "Required CLI the user must install." }
  ]
}
```

The installer uses this to:

- copy/symlink the folder into the agent's skills directory,
- place each `commands/*.md` into the agent's commands directory,
- create a Python venv and install `requirements.txt` if present,
- regenerate the `<!-- BEGIN SkillsForAgents:auto-managed -->` block in `CLAUDE.md` / `AGENTS.md` so the trigger phrases are wired up.

## Path conventions

Don't hardcode `/Users/<you>/...` paths anywhere. For locations inside the skill itself, use `$SKILL_DIR` (the installer points it at the install location) and fall back to `~/.claude/skills/<name>` on Claude Code if the variable isn't set. For user-side knowledge bases, read the path from `$OBSIDIAN_BRAIN_PATH` or `~/.config/skills-for-agents/brain-path`.

## Test locally before opening a PR

```bash
./install.sh --agent claude --only <name> --mode copy --brain /tmp/test-brain -y
```

Verify the skill folder lands under `~/.claude/skills/<name>/`, the commands appear in `~/.claude/commands/`, and the `CLAUDE.md` trigger block lists your new skill.
