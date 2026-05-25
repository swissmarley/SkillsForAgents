---
name: session-journal
description: Record and archive work sessions into an Obsidian-style brain/wiki. Activation phrase "Hey Claude, let's go!" — closing phrase "I'm done for today" (case-insensitive, may be embedded in a longer message).
type: flexible
---

# Session Journal

Manage recording and archival of work sessions in an Obsidian-style brain/wiki, accessible from any directory.

## Configuration

This skill expects an Obsidian-style vault. Resolve the vault root in this order:

1. `$OBSIDIAN_BRAIN_PATH` environment variable
2. `~/.config/skills-for-agents/brain-path` (single-line file with the path)
3. Default: `~/Documents/Obsidian/Brain`

Inside the vault, this skill writes to:

- Journal: `<brain>/wiki/journal/`
- Index: `<brain>/wiki/index.md`
- Log: `<brain>/wiki/log.md`

Create directories on first run if they don't exist.

## Phase 1 — Activation

If the user message contains **"Hey Claude, let's go!"** (case-insensitive, or similar variants like "Claude, start", "let's begin recording"):

1. Confirm briefly: _"Session recording started. When you're done, say 'I'm done for today' and I'll archive everything."_
2. Continue working normally. Keep mental track of:
   - Topics discussed
   - Decisions made
   - Open questions
   - Ideas or insights that emerged
   - Tasks and actions mentioned
3. No need to remind the user that you're recording — just stay aware for the final summary.

## Phase 2 — Closing and archival

If the user message contains **"I'm done for today"** (case-insensitive, may be embedded in a longer message):

### 2.1 Generate the session file

Create `<brain>/wiki/journal/YYYY-MM-DD.md` (today's date) with this structure:

```markdown
---
tags: [journal, session]
date: YYYY-MM-DD
sources: []
status: active
---

# Session of YYYY-MM-DD

## Summary
[Paragraph summarizing what was done and discussed]

## Topics covered
- **Topic 1** — brief description
- **Topic 2** — brief description

## Decisions made
- Decision 1
- Decision 2

## Open questions
- Question 1
- Question 2

## Roadmap
[Future work, planned next sessions — leave a dash if nothing emerged]

## Tasks and actions
- [ ] task 1
- [ ] task 2

## Additional notes
[Leave empty — the user will complete with personal reflections]
```

### 2.2 Fill the sections

- **Summary**: one paragraph synthesizing the session
- **Topics covered**: bullet list of main themes touched
- **Decisions made**: what was decided during the session
- **Open questions**: what remains to be explored or resolved
- **Roadmap**: next steps, planned work (use "—" if nothing emerged)
- **Tasks and actions**: concrete actions, ideally with `- [ ]` checkboxes
- **Additional notes**: leave empty

### 2.3 Confirm with the user

After writing the file, ask:
_"Saved the session to [[wiki/journal/YYYY-MM-DD]]. Want to add anything to the notes, roadmap, or tasks before I archive everything?"_

If the user provides additions, update the file.

### 2.4 Update index.md

Read `<brain>/wiki/index.md` and add (or update) the `## Journal` section with:

```markdown
## Journal
- [[journal/YYYY-MM-DD]] — Session of YYYY-MM-DD. [list of main themes]. 0 sources.
```

If `## Journal` doesn't exist, create it as the last section.

### 2.5 Update log.md

Append to the end of `<brain>/wiki/log.md`:

```
## [YYYY-MM-DD] journal | Session

- Created: [[wiki/journal/YYYY-MM-DD]]
- Topics: comma-separated list of main themes
- Key outcome: the most important result or insight from the session
```

## Edge cases

**User wants to close but doesn't use the exact phrase**: if you notice closing signals ("that's it for now", "we're done", "let's wrap up") without "I'm done for today", ask gently: _"Want me to archive this session, or keep going?"_

**User says "Hey Claude, let's go!" while a session is already active**: treat the new phrase as a reset — close the previous session and open a new one. If it wasn't archived, warn: _"I had an unarchived session open. I'll close it and start a new one."_

**User says "I'm done for today" without having activated**: archive anyway with the current conversation contents — don't complain about the missing activation.
