---
name: wiki-save
description: Save content, ideas, or relevant information into an Obsidian-style brain/wiki on explicit user request. Triggers "save this", "save to wiki", "archive this", "add to wiki", "/save" or similar.
type: flexible
---

# Wiki Save

Archive content into an Obsidian-style brain/wiki on explicit user request. Triggers: "save this", "save to wiki", "archive this", "add to wiki", "/save", or similar phrases.

## Configuration

Resolve the vault root in this order:

1. `$OBSIDIAN_BRAIN_PATH` environment variable
2. `~/.config/skills-for-agents/brain-path` (single-line file with the path)
3. Default: `~/Documents/Obsidian/Brain`

Inside the vault, this skill writes to:

- Index: `<brain>/wiki/index.md`
- Log: `<brain>/wiki/log.md`
- Concepts: `<brain>/wiki/concepts/`
- Entities: `<brain>/wiki/entities/`
- Synthesis: `<brain>/wiki/synthesis/`
- Reflections: `<brain>/wiki/reflections/`

Create directories on first run if they don't exist.

## Flow

### 1. Understand what to save

The user is asking to save something. Identify:

- **Content**: what exactly is to be saved? An idea, a fact, an insight, a decision, a reference?
- **Scope**: the immediately previous message? A summary of recent exchanges? Something specific the user mentioned?
- **Page type**: is it a concept, an entity, a synthesis, or a reflection?

If unclear, ask briefly.

### 2. Determine the category and file

| Category | When to use | File name |
|---|---|---|
| `concepts/` | Ideas, principles, patterns, mental frameworks | `concept-name.md` (kebab-case) |
| `entities/` | People, books, tools, programs, organizations | `entity-name.md` (kebab-case) |
| `synthesis/` | Comparisons, cross-cutting analyses, links between ideas | `topic-synthesis.md` (kebab-case) |
| `reflections/` | Personal notes, journal, subjective thoughts | `reflection-theme.md` (kebab-case) |

Ask the user: _"Where should I archive this? Concept, entity, synthesis, or reflection?"_ — or, if it's obvious from context, proceed and just inform the user of the choice.

### 3. Create or update the page

Every page must have complete YAML frontmatter:

```yaml
---
tags: [tag1, tag2, tag3]
date: YYYY-MM-DD
sources: []
status: draft
---
```

If the page already exists:
- Read it first
- Add new content coherently
- Update `date` and `status` in the frontmatter
- Add `[[wikilinks]]` connecting to related pages where appropriate

If it's a new page:
- Create the file with frontmatter and initial content
- Use `[[wikilinks]]` to connect to other wiki pages
- Leave space for future expansion

**File names**: always kebab-case in English.

### 4. Update index.md

Read `<brain>/wiki/index.md` and add or update the entry in the appropriate section:

```markdown
- [[category/page-name]] — Short description (one line). 1 source. Updated YYYY-MM-DD.
```

If the category doesn't yet have a section in the index, create it.

### 5. Update log.md

Append to the end of `<brain>/wiki/log.md`:

```
## [YYYY-MM-DD] save | [Content title]

- Created: [[wiki/category/page-name]]
- Content: very brief description of what was saved
```

### 6. Confirm

Confirm to the user: _"Saved to [[category/page-name]]. Want me to add anything else?"_

## Examples

**User**: "save this — the pomodoro technique helps me stay focused"
**Response**: Create/update `wiki/concepts/pomodoro-technique.md`, tags: `[productivity, focus, techniques]`

**User**: "/save to wiki: today I realized I delegate too little because I'm afraid of losing control"
**Response**: Create `wiki/reflections/delegation-and-control.md`, tags: `[delegation, control, personal-growth]`

**User**: "archive this link as a source"
**Response**: Save the source in `raw/`, then create/update the linked wiki pages.
