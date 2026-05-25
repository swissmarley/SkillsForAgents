# Tool Builder — Per-tool Sub-flow

This is the loop you run inside SKILL.md Stage 1.4 (and Flow 2). Repeat for every custom tool the agent needs.

## Inputs you must collect from the user

Ask one question at a time:

1. **Tool name** (snake_case) — e.g. `create_calendar_event`
2. **What does it do** (one sentence) — becomes the `function.description`. The voice agent's LLM uses this to decide *when* to call the tool, so make it crisp and outcome-focused: "Books a meeting in the personal Google Calendar."
3. **Action type** — pick from menu:
   - `gmail_send` / `gmail_list` / `gmail_reply`
   - `gcal_create` / `gcal_list_events` / `gcal_update` / `gcal_delete`
   - `http_request` (any external API)
   - `database_query` (Postgres/MySQL/etc.)
   - `slack_post`
   - `custom` (free-form n8n nodes)
4. **Parameters** — name, type (string/number/array/boolean), required?, description. Loop until the user says "done".
5. **Credentials** — for any auth-bound action (Gmail, Calendar, DB), confirm the user has the credential preconfigured in n8n. If not, pause and direct them to n8n → Credentials → New, then resume.

## Steps to execute (in order)

### Step A — Generate the Vapi tool definition

Write `./vapi-build-out/<agent-slug>/tools/<tool_name>.vapi.json`:

```json
{
  "type": "function",
  "function": {
    "name": "<tool_name>",
    "description": "<one-sentence description>",
    "parameters": {
      "type": "object",
      "properties": { /* from Step 4 */ },
      "required": [ /* from Step 4 */ ]
    }
  },
  "server": {
    "url": "WILL_BE_FILLED_AFTER_N8N_DEPLOY"
  }
}
```

### Step B — Generate a UUID for the n8n webhook

```bash
uuidgen | tr '[:upper:]' '[:lower:]'
```

This becomes both the n8n Webhook node's `path` and `webhookId`, and the tail of the production URL.

### Step C — Build the n8n workflow JSON

Start from `assets/workflow-template.json`. Customize:

1. **Webhook node** — replace `<UUID>` (path + webhookId) with Step B's UUID
2. **Validate Input code node** — generate JS that:
   - Pulls `vapiArgs` from `body.message.toolCallList[0].function.arguments` with full fallback chain (see `n8n-workflow-guide.md` §4.1)
   - Throws `Error('<param> is required')` for each required parameter
   - Applies type coercion (arrays → comma strings for Gmail; arrays → `[{email}]` for Calendar attendees)
   - Returns one item with the cleaned fields
3. **Action node** — pick the right n8n node + typeVersion:
   - Gmail send: `n8n-nodes-base.gmail` `typeVersion: 2.1`
   - Gmail get: same, with `format: "resolved"`
   - Google Calendar: `n8n-nodes-base.googleCalendar` `typeVersion: 1.2`, attendees mapped as `[{email}]`
   - HTTP: `n8n-nodes-base.httpRequest` `typeVersion: 4.2`
   - DB: `n8n-nodes-base.postgres` / `n8n-nodes-base.mysql`
   Reference outputs of node 2 with `={{ $json.<field> }}`.
4. **Format Response code node** — must use `$('Webhook').first().json` for `toolCallId`, never `$input`. Wrap the result with `JSON.stringify(...)`. Return the `{ results: [{ toolCallId, result }] }` envelope.
5. **Respond to Webhook node** — `respondWith: "json"`, `responseBody: "={{ JSON.stringify($json) }}"`, `responseCode: 200`.
6. **Connections** — verify the chain: `Webhook → Validate Input → Action → Format Response → Respond to Vapi`. The string `"Respond to Vapi"` must appear as a node target inside `connections`.

Write the workflow JSON to `./vapi-build-out/<agent-slug>/tools/<tool_name>.n8n.json`.

### Step D — Push the workflow into n8n

Use whichever method is available, in this order:

#### D.1 — n8n MCP (preferred)

If an n8n MCP server is connected, call its create-workflow tool with the JSON. Typical surfaces:
- `n8n.workflows.create({ workflow: <json> })` → returns `id`
- `n8n.workflows.activate({ id })` → flips to Active
- `n8n.workflows.get({ id })` → confirms `active: true`

Save the returned workflow id.

#### D.2 — n8n REST API (fallback)

If the user provided base URL + API key:

```bash
# Create
curl -sS -X POST "$N8N_BASE/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_KEY" \
  -H "Content-Type: application/json" \
  -d @<tool_name>.n8n.json | jq -r .id

# Activate (CRITICAL — active:true in JSON is ignored on import)
curl -sS -X POST "$N8N_BASE/api/v1/workflows/<id>/activate" \
  -H "X-N8N-API-KEY: $N8N_KEY"
```

#### D.3 — Manual import (last resort)

Tell the user: "Open n8n → Workflows → Import from File → pick `tools/<tool_name>.n8n.json`. Then assign credentials to the action node, toggle Active ON, and save (Ctrl+S)."

### Step E — Resolve credentials

For Gmail / Calendar / DB nodes, the JSON we generated has placeholder credential ids. The user must select the real credential in the n8n UI **once per tool**. Pause the flow and confirm: "Open the workflow in n8n, click the action node, pick the credential from the dropdown, save. Reply `done` when ready."

### Step F — Smoke test the Production URL

The Production URL is always `${N8N_BASE}/webhook/<UUID>`. Run:

```bash
curl -sS -X POST "$N8N_BASE/webhook/<UUID>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "toolCallList": [{
        "id": "smoketest_001",
        "function": {
          "name": "<tool_name>",
          "arguments": { /* a realistic minimal payload */ }
        }
      }]
    }
  }'
```

Required passing response shape:
```json
{ "results": [ { "toolCallId": "smoketest_001", "result": "<json string>" } ] }
```

If the response doesn't match, walk the user through `n8n-workflow-guide.md` §10 Step 2 failure table. **Do not move on** until smoke test passes.

### Step G — Wire the URL into the Vapi tool

Open `./vapi-build-out/<agent-slug>/tools/<tool_name>.vapi.json`, replace `WILL_BE_FILLED_AFTER_N8N_DEPLOY` with `${N8N_BASE}/webhook/<UUID>`. This file gets merged into the assistant's `tools` array in Stage 1.5.

### Step H — Append a checklist line to BUILD_SUMMARY.md

```
- ✅ <tool_name> — n8n workflow id <wfId>, prod URL https://.../webhook/<UUID>, smoke test 200
```

## Quick reference: type coercion cheatsheet

| Vapi sends | n8n action expects | Code node line |
|---|---|---|
| `to: ["a@x", "b@x"]` | Gmail comma string | `Array.isArray(args.to) ? args.to.join(',') : args.to` |
| `participants: ["a@x"]` | Calendar `[{email}]` | `={{ $json.participants.map(e => ({email: e})) }}` |
| `sinceDateTime: "2026-05-01T00:00:00Z"` | Gmail `after:<unix>` | `' after:' + Math.floor(new Date(args.sinceDateTime).getTime()/1000)` |
| `sendInvites: true` | Calendar `sendUpdates` | `={{ $json.sendInvites ? 'all' : 'none' }}` |
