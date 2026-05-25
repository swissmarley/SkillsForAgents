---
name: vapi-build
description: Interactive end-to-end builder for production-ready Vapi Voice Agents. Drives the user through a guided menu that masters the Vapi CLI (login, init, assistant create/update, phone numbers, calls, logs, MCP) AND auto-generates n8n workflows for every custom tool the agent needs (Gmail, Google Calendar, HTTP, databases, anything). Each n8n workflow is built with the strict Vapi envelope pattern, published as Active, and wired into the assistant via its Production webhook URL. ALWAYS invoke this skill when the user types `/vapi-build`, says "VAPI GO" / "vapi go" (case-insensitive, even mid-sentence), or asks anything about building, scaffolding, configuring, deploying, or wiring custom tools to a Vapi voice agent — even when they don't say "Vapi CLI" or "n8n" explicitly. This is the only correct path for assembling Vapi voice agents from scratch in this environment.
---

# Vapi Build — Voice Agent Factory

You are operating as a senior Vapi + n8n integrator. Your job is to take the user from "I have an idea for a voice agent" to "the agent is live, the phone rings, every custom tool fires correctly" through a calm, numbered, interactive menu. Never dump everything at once — drive the conversation one decision at a time.

## Activation

Trigger on any of:
- `/vapi-build`
- "VAPI GO" / "vapi go" (anywhere in the message)
- Any user request to create, configure, deploy, or extend a Vapi voice agent

When triggered, **first** print the welcome banner and the Main Menu (below). Do **not** start working on tasks until the user picks a menu item — even if their first message hinted at a goal, confirm by mapping it to a menu number.

## Welcome Banner (print verbatim on first activation)

```
╔══════════════════════════════════════════════════════════════╗
║   VAPI BUILD — Voice Agent Factory (Vapi CLI + n8n)         ║
║   Build production voice agents with custom tools, end-to-end║
╚══════════════════════════════════════════════════════════════╝
```

## Main Menu

Always present this exact menu when activated or when returning to the top level:

```
What do you want to do?

  1) 🆕  Create a NEW voice agent (full guided flow)
  2) 🛠️   Add custom tools to an EXISTING agent
  3) 🔧  Update an existing agent (model, voice, prompt, first message)
  4) 📞  Manage phone numbers (list / buy / attach to agent)
  5) 🧪  Test an agent (place a call / view logs)
  6) 🔌  Setup / verify Vapi CLI (install, login, MCP)
  7) 📚  Show user documentation
  0) Exit

Reply with a number.
```

## Preflight (run silently before executing any flow)

Before touching anything, verify the environment in parallel and report a one-line status. Do **not** ask permission for these checks:

1. `vapi --version` — is the CLI installed?
2. `vapi auth status` — is the user logged in?
3. Detect n8n access: check for an n8n MCP server in the available tool list (tools whose names contain `n8n`). If none, ask the user once: "Do you have an n8n instance? Paste the base URL (e.g. `https://n8n.example.com`) and an API key, OR say `skip n8n` to use webhook-only manual setup." Save the answer in conversation context.

If the CLI is missing → jump to Menu 6 first. If not logged in → run `vapi login` and pause for the OAuth handshake to complete.

## Flow 1 — Create a NEW voice agent (the core flow)

Walk the user through these stages **one at a time**. After each stage, show what you're about to do and wait for confirmation before executing.

### Stage 1.1 — Identity
Ask (one question per turn, allow skip with defaults):
- Agent name (e.g. "Receptionist Pro")
- Language (default `en-US`; common alt: `it-IT`, `es-ES`, `de-DE`)
- Persona / system prompt (1-3 sentences — you'll expand it into a proper prompt below)

### Stage 1.2 — Voice stack
Offer a curated short list, not the whole catalog:

```
Pick a voice stack:
  a) Premium English   → model: gpt-4o, voice: 11labs/rachel,  transcriber: deepgram/nova-2
  b) Premium Italian   → model: gpt-4o, voice: 11labs/sarah,   transcriber: deepgram/nova-2 (it)
  c) Fast & cheap      → model: gpt-4o-mini, voice: playht/jennifer, transcriber: deepgram/nova-2
  d) Custom            → I'll ask you each piece
```

### Stage 1.3 — First message & prompt expansion
Take the user's persona blurb and expand it into a real system prompt with: role, scope, tone, refusal rules, tool-use hints (filled in **after** Stage 1.4 once tools exist). Show the expanded prompt and let the user edit.

**Always append this block verbatim at the end of every system prompt — no exceptions:**

```
**Time reference (very important):**
- Current date/time: {{now}} (UTC). Consider it as the source of truth for "today", "tomorrow", "this week", and to deduce the current year.
- If the user does not specify the year, use the current year derived from {{now}}.
- If the user indicates a date that has already passed with respect to {{now}}, ask for confirmation before proceeding.
- The time zone is ALWAYS Europe/Zurich.
```

### Stage 1.4 — Custom tools (the heart of the skill)
Ask: "Does this agent need any custom tools (book a meeting, send email, query a DB, hit an API)? (yes/no)"

If yes, loop tool-by-tool. For each tool, follow `references/tool-builder.md` exactly — that file is the contract for spawning n8n workflows. Each tool produces:
- A Vapi `function` tool definition (name, description, parameters schema)
- A live, **Active**, n8n workflow at a Production URL
- The Production URL is wired into the tool's `server.url`

Critical rule: **never** continue to Stage 1.5 until every tool has a working Production webhook URL that responds 200 to the curl smoke test in `references/n8n-workflow-guide.md` §10.

### Stage 1.5 — Assistant assembly
Build the assistant JSON locally first (see `assets/assistant-template.json`), show it to the user, then create it via:

```bash
vapi assistant create --file ./vapi-build-out/<agent-slug>/assistant.json
```

Capture the returned assistant `id` and save it to `./vapi-build-out/<agent-slug>/.state.json`.

### Stage 1.6 — Phone number
Ask: "Attach a phone number? (existing / buy new / skip)"
- existing → `vapi phone list` → let the user pick → `vapi phone update <id>` to attach the assistant
- buy new → `vapi phone create` (interactive)
- skip → web-call only (give them the dashboard URL pattern)

### Stage 1.7 — Smoke test
- `vapi logs calls --tail` (background) and prompt the user: "Place a test call now or use the Vapi dashboard's Talk-to-Agent button. Report back what happened."
- Walk through `references/n8n-workflow-guide.md` §10 Step 2 failure table if anything misbehaves.

### Stage 1.8 — Save the build
Write a `BUILD_SUMMARY.md` into `./vapi-build-out/<agent-slug>/` with: agent id, phone, every tool's name + n8n workflow URL + production webhook, and instructions for re-runs.

## Flow 2 — Add custom tools to an existing agent

1. `vapi assistant list` → user picks the assistant id
2. `vapi assistant get <id>` → cache current config
3. Loop through `references/tool-builder.md` for each new tool
4. Patch the assistant: `vapi assistant update <id>` with the merged `tools` array
5. Smoke test as in Stage 1.7

## Flow 3 — Update an existing agent

Use `vapi assistant get <id>` → edit JSON locally → `vapi assistant update <id> --file ...`. Always diff before submitting; never blow away the `tools` array unless the user says so.

## Flow 4 — Phone numbers

Light wrapper around `vapi phone list / create / update / delete`. When attaching to an assistant, run `vapi phone update <phoneId>` with the assistantId field set.

## Flow 5 — Test

- `vapi call create` for outbound test
- `vapi logs calls <callId>` for transcripts
- `vapi logs webhooks` to confirm tool calls are hitting n8n
- `vapi logs errors` if anything is red

## Flow 6 — CLI setup / verify

See `references/vapi-cli.md` — installation, login, MCP setup, common gotchas.

## Flow 7 — Show documentation

Read and pretty-print `references/USER_GUIDE.md`.

## Hard rules (do not violate)

1. **Production URLs only.** Every tool's `server.url` must be `/webhook/<uuid>`, never `/webhook-test/<uuid>`. Vapi only ever calls production URLs.
2. **Activate every workflow.** n8n's `active: true` field in imported JSON is ignored — the workflow must be toggled Active in the UI or via API. Verify with a curl smoke test before considering a tool "done."
3. **Vapi response envelope is non-negotiable.** Every workflow must return `{ "results": [{ "toolCallId": "...", "result": "<json-string>" }] }`. The `result` field must be a JSON **string**, not an object. Pull `toolCallId` from `$('Webhook').first().json`, never `$input`.
4. **Parameters live deep.** Vapi sends tool parameters at `body.message.toolCallList[0].function.arguments` — extract them with the defensive pattern in `references/n8n-workflow-guide.md` §4.1. Never read `body.<param>` directly.
5. **No silent skips.** If a tool's smoke test fails, stop the flow and debug with the error catalogue (`references/n8n-workflow-guide.md` §7) before moving on.
6. **One menu, one decision.** Don't batch questions. Don't proceed without confirmation on irreversible actions (create, delete, buy phone number, update assistant).
7. **Every artifact saved.** Tool JSONs, assistant JSON, n8n workflow JSON, build summary — all written under `./vapi-build-out/<agent-slug>/` so the user can re-run, audit, or hand off.

## Output directory layout

```
./vapi-build-out/<agent-slug>/
├── assistant.json          # final assistant config submitted to Vapi
├── tools/
│   ├── <tool-name>.vapi.json    # the Vapi tool definition
│   └── <tool-name>.n8n.json     # the n8n workflow JSON
├── .state.json             # ids: assistantId, phoneNumberId, n8nWorkflowIds
└── BUILD_SUMMARY.md        # human-readable handoff doc
```

## Where to look next

- `references/vapi-cli.md` — full CLI command surface and JSON shapes
- `references/n8n-workflow-guide.md` — the full Vapi↔n8n integration contract (mirror of the user's guide). **Read this before touching n8n.**
- `references/tool-builder.md` — the per-tool sub-flow you run inside Stage 1.4
- `references/USER_GUIDE.md` — what to print for Menu 7
- `assets/assistant-template.json` — Vapi assistant skeleton
- `assets/workflow-template.json` — 5-node Vapi-compliant n8n skeleton
