---
name: magic-content
description: Interactive research pipeline. Discovery on YouTube/Web/PDF for a topic, content generation with NotebookLM (briefing/study guide/FAQ/mind map/audio/video/timeline), artifact review, ingest into an Obsidian-style brain/wiki. Triggers /magic-content or "MAGIC <topic>".
---

# Magic Content Pipeline

You are running an interactive research pipeline. Follow these steps in order. At every checkpoint use `AskUserQuestion` to get the user's decision — never auto-pick.

## Configuration

Resolve the Obsidian-style brain root in this order:

1. `$OBSIDIAN_BRAIN_PATH` environment variable
2. `~/.config/skills-for-agents/brain-path` (single-line file with the path)
3. Default: `~/Documents/Obsidian/Brain`

Throughout this document, `<brain>` refers to the resolved path.

## Setup

- Skill scripts: this skill's own `scripts/` directory. The installer exports `$SKILL_DIR` for this skill — fall back to `~/.claude/skills/magic-content` on Claude Code if unset. Run with `$SKILL_DIR/.venv/bin/python <script>` (the installer creates the venv and installs `requirements.txt`).
- Brain repo: `<brain>/`
- Per-run temp dir: `WORK=/tmp/magic-content/$(date +%s)-$$` ; `mkdir -p "$WORK"`
- All scripts emit JSON on stdout. Non-zero exit means error — read the error JSON.

Sanity-check NotebookLM auth before anything else:
```bash
notebooklm status
```
If not authenticated, stop and tell the user to run `notebooklm login`.

## Step 1 — Determine the topic

- Invoked as `MAGIC <topic>`: extract `<topic>` from the user message (case-insensitive; may be embedded in longer text)
- Invoked as `/magic-content` (no arg) or `MAGIC` alone: use `AskUserQuestion` — single open-ended "What topic do you want to research?" (use the "Other" option for free text)

Then:
```bash
SLUG=$(python "$SKILL_DIR/scripts/slugify.py" "<topic>")
```

## Step 2 — Generate 2-3 alternative search queries

Reason about the topic. Produce 2-3 distinct query strings with different angles (e.g., for "transformer attention": "transformer attention mechanism", "self-attention explained", "multi-head attention deep learning"). Save as JSON list:
```bash
cat > "$WORK/queries.json" <<'EOF'
["query 1", "query 2", "query 3"]
EOF
```

## Step 3 — Run discovery (WebSearch + merge)

For EACH query, call `WebSearch` three times (three channels) and accumulate results:
1. `WebSearch(query="site:youtube.com <q>")` → save normalized list `[{url, title, snippet}]` to `$WORK/youtube_raw.json`
2. `WebSearch(query="<q>")` → `$WORK/web_raw.json`
3. `WebSearch(query="<q> filetype:pdf")` → `$WORK/pdf_raw.json`

Each WebSearch returns Google-style results. Normalize them to `[{"url": "...", "title": "...", "snippet": "..."}]` before writing to file.

Merge & enrich:
```bash
python "$SKILL_DIR/scripts/search.py" merge \
    --topic "<topic>" \
    --queries-json "$WORK/queries.json" \
    --youtube-results "$WORK/youtube_raw.json" \
    --web-results "$WORK/web_raw.json" \
    --pdf-results "$WORK/pdf_raw.json" \
    --enrich-youtube \
    > "$WORK/candidates.json"
```

If a channel is empty in `candidates.json`, mention it but proceed. If ALL channels are empty, use `AskUserQuestion`: rephrase query / enter URLs manually / cancel.

## Step 4 — Source selection (checkpoint)

Read `$WORK/candidates.json`. Build a multi-select `AskUserQuestion` showing each candidate with:
- Channel header (YouTube / Web / PDF)
- Title
- URL (truncated to ~80 chars in the label)
- For YouTube: channel name + duration if available
- For Web/PDF: snippet preview

Add a final option "Cancel run".

Save selected entries to `$WORK/selected_sources.json` as `[{type, url, title}]`.

## Step 5 — Artifact selection (checkpoint)

Use `AskUserQuestion` (multi-select) with these 7 canonical IDs and labels:
- `briefing` — Briefing Doc
- `study_guide` — Study Guide
- `faq` — FAQ
- `mind_map` — Mind Map
- `audio` — Audio Overview (Podcast)
- `video` — Video Overview
- `timeline` — Timeline

Save chosen IDs to `$WORK/artifact_types.json`.

## Step 6 — Download selected PDFs

If any selected source has `type: "pdf"`:
1. Build a JSON list of just the PDF entries: `$WORK/selected_pdfs.json`
2. Run:
```bash
python "$SKILL_DIR/scripts/pdf_download.py" \
    --urls-json "$WORK/selected_pdfs.json" \
    --dest "$WORK/pdfs/"
```
3. Show the `downloaded`/`failed` summary. If many failed, ask via `AskUserQuestion` whether to proceed.

## Step 7 — NotebookLM run

```bash
# Create notebook (positional title)
NB_OUT=$(python "$SKILL_DIR/scripts/nblm.py" create \
    --name "magic-${SLUG}-$(date +%Y%m%d)")
NB_ID=$(echo "$NB_OUT" | python -c "import json,sys;print(json.load(sys.stdin)['notebook_id'])")

# Build $WORK/nblm_sources.json from selected_sources.json + downloaded PDFs:
#   - YouTube/Web entries: {"type": "url", "value": "<url>"}
#   - PDF entries (downloaded): {"type": "file", "value": "<absolute path>"}
# (You build this JSON.)

python "$SKILL_DIR/scripts/nblm.py" add-sources \
    --notebook "$NB_ID" --sources-json "$WORK/nblm_sources.json"

# Wait for sources to be processed
python "$SKILL_DIR/scripts/nblm.py" wait \
    --notebook "$NB_ID" --timeout 300
```

If `wait` returns `{"ready": false, "error": "timeout"}`, use `AskUserQuestion`: retry wait / continue anyway / cancel.

### Generate artifacts

For each ID in `$WORK/artifact_types.json`, invoke the appropriate CLI command (the `nblm.py generate` wrapper handles audio/video/mind_map directly; for `briefing`/`study_guide`/`faq`/`timeline` we call `notebooklm generate report` directly with the right `--format`):

```bash
mkdir -p "$WORK/artifacts"

for TYPE in $(cat "$WORK/artifact_types.json" | python -c "import json,sys;print(' '.join(json.load(sys.stdin)))"); do
  case "$TYPE" in
    audio|video|mind_map)
      # For mind_map, the CLI subcommand is "mind-map" with a hyphen
      CLI_TYPE=$(echo "$TYPE" | tr '_' '-')
      python "$SKILL_DIR/scripts/nblm.py" generate \
          --notebook "$NB_ID" --types "$CLI_TYPE"
      ;;
    briefing)
      notebooklm generate report -n "$NB_ID" --format briefing-doc --no-wait --json
      ;;
    study_guide)
      notebooklm generate report -n "$NB_ID" --format study-guide --no-wait --json
      ;;
    faq)
      notebooklm generate report -n "$NB_ID" --format custom \
          "Create an FAQ document with key questions readers would ask about this topic and clear, comprehensive answers" \
          --no-wait --json
      ;;
    timeline)
      notebooklm generate report -n "$NB_ID" --format custom \
          "Create a chronological timeline of key events, developments, milestones, and turning points related to this topic" \
          --no-wait --json
      ;;
  esac
done
```

Wait briefly (NotebookLM generation is async; `--no-wait` returns immediately). Use `AskUserQuestion` to ask the user to wait — typical times: text reports ~30s, audio ~1-3 min, video ~3-10 min. You can poll status by re-running `notebooklm source list` (artifacts also appear there in some CLI versions) or just wait a fixed amount of time then proceed to download.

### Download artifacts

```bash
python "$SKILL_DIR/scripts/nblm.py" download \
    --notebook "$NB_ID" --dest "$WORK/artifacts/"
```

If a download error mentions "no artifacts" for a type, that's normal for types that weren't generated — the wrapper tolerates this.

If any step returns `{"error": "auth_expired", ...}`, stop and tell the user to run `notebooklm login`.

## Step 8 — Artifact review (checkpoint with regenerate loop)

For each downloaded file in `$WORK/artifacts/`:
- If text (`.md`, `.txt`): `Read` the file and show the user a 30-line preview
- If binary (`.mp3`, `.mp4`, `.png`): show file path + size + type only

Use `AskUserQuestion` per artifact: `Accept` / `Edit` / `Discard`. If `Edit`, present the file content in a code block, get the user's edit, write back to the file.

After all artifacts handled, ask globally via `AskUserQuestion`:
- `Proceed to wiki ingest`
- `Regenerate with different sources` → loop back to Step 4 (preserve `$WORK/candidates.json`)
- `New query (restart search)` → loop back to Step 2
- `Cancel`

## Step 9 — Manifest + final placement

Build `$WORK/manifest_input.json` combining `<topic>`, `$SLUG`, queries, selected_sources (sanitized to `[{type, url, title}]`), artifacts (`[{type, file: "<filename>"}]` based on accepted artifacts), `$NB_ID`, today's date.

```bash
BRAIN="${OBSIDIAN_BRAIN_PATH:-$HOME/Documents/Obsidian/Brain}"
SLUG_OUT=$(python "$SKILL_DIR/scripts/manifest.py" write \
    --raw-root "$BRAIN/raw/notebooklm" \
    --input-json "$WORK/manifest_input.json")
SLUG_DIR=$(echo "$SLUG_OUT" | python -c "import json,sys;print(json.load(sys.stdin)['slug_dir'])")

# Move accepted artifacts from $WORK/artifacts/ into the resolved slug dir
mv "$WORK/artifacts/"* "$SLUG_DIR/"
```

## Step 10 — Cleanup temp dir

```bash
rm -rf "$WORK"
```

(Cleanup failure is non-fatal.)

## Step 11 — Hand off to standard CLAUDE.md ingest

Read `<brain>/CLAUDE.md` (the user's own brain-level instructions, if any) and follow its **Ingest** workflow on the new `raw/notebooklm/<slug>/`. If no such file exists, apply this default flow:

1. Verify the slug dir is NOT yet in `<brain>/wiki/processed.md`
2. Read `manifest.json` and the artifact files
3. Draft the wiki pages — primary concept page from the briefing doc; entity pages for prominent people/tools mentioned; synthesis page if cross-cutting
4. **Critical checkpoint**: use `AskUserQuestion` for each draft `.md` BEFORE writing into `<brain>/wiki/`
5. Per page: Accept / Edit / Discard
6. After all accepted: write to `<brain>/wiki/`, update `<brain>/wiki/index.md`, append entry to `<brain>/wiki/processed.md` and `<brain>/wiki/log.md`

When linking audio/video/mind-map assets in concept pages, use Obsidian embeds:
```markdown
![[raw/notebooklm/<slug>/podcast.mp3]]
```

## Step 12 — Confirm completion

Tell the user: pages created, the `notebook_id` (so they can chat with the notebook in NotebookLM web UI for follow-up), and source/artifact counts.

## Smoke test (run once after install)

Topic: small ("vector embeddings basics")
- 1 web URL + 1 YouTube URL
- Generate only Briefing Doc
- Verify a wiki page lands in `<brain>/wiki/concepts/` and `<brain>/wiki/processed.md` is updated

## Error recovery cheatsheet

| Symptom | Action |
|---|---|
| `notebooklm status` fails | Tell user to run `notebooklm login` |
| `search.py` returns all-empty channels | `AskUserQuestion`: rephrase / manual URLs / cancel |
| `pdf_download.py` has many failed | Show list, ask whether to continue |
| `nblm.py wait` returns timeout | `AskUserQuestion`: retry / continue without / cancel |
| Generation taking too long | Wait longer; audio/video can take 5-10 min |
| Slug collision | `manifest.py` auto-suffixes; just use returned `slug_dir` |
| Crash mid-run | `/tmp` debris is harmless; if `raw/notebooklm/<slug>/` exists from prior partial run, ingest workflow will skip it (or you can move it aside before retry) |
