---
description: Save content to your Obsidian-style brain/wiki
---

Invoke the `wiki-save` skill via the Skill tool. The skill identifies what to save (from the immediately preceding context or explicit user input), asks where to file it (concept / entity / synthesis / reflection), writes the page with proper frontmatter, updates `index.md` and `log.md`, then confirms.

If the user passed arguments after `/save`, treat them as the content to save.
