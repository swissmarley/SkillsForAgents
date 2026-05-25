# Building n8n Workflows as Vapi Custom Tool Backends: Complete Implementation Guide

> **Version 2.0** — Updated after full end-to-end production validation. All patterns in this document are verified working with Vapi Voice Agents and n8n self-hosted instances.

## Overview

This guide documents the correct procedure for building n8n workflows that serve as backend execution engines for Vapi Voice Agent Custom Tools. It is written as a reference for AI coding agents (Claude Code, GPT-4, Cursor, etc.) and human developers, and covers the full lifecycle: from reading a Vapi tool definition to a fully working, production-activated n8n workflow. Every error encountered during real-world debugging is catalogued with its fix.

---

## 1. Understanding the Architecture

### 1.1 How Vapi Custom Tools Work

When a Vapi Voice Agent decides to call a Custom Tool during a conversation, it performs an HTTP POST request to the `server.url` defined in the tool's JSON configuration. The request body contains:

- The tool parameters, nested inside `message.toolCallList[0].function.arguments`
- A `message` object with a `toolCallList` array, where each entry has a unique `id` (the `toolCallId`)

The n8n workflow must:
1. Receive this POST request via a Webhook node
2. Extract the tool parameters from the correct nested path
3. Execute the required action (email, calendar, database, API call, etc.)
4. Return a response in the **exact Vapi envelope format** within the HTTP response

### 1.2 Data Flow Diagram

```
Vapi Voice Agent
      │
      │  HTTP POST (JSON body — parameters nested in message.toolCallList[0].function.arguments)
      ▼
n8n Webhook Node  (production URL: /webhook/<uuid>)
      │
      ▼
Code Node: Validate & Extract Parameters  ← extracts from vapiArgs path
      │
      ▼
Action Node: Gmail / Google Calendar / HTTP Request / etc.
      │
      ▼
Code Node: Format Response (build Vapi envelope with toolCallId)
      │
      ▼
Respond to Webhook Node  (returns JSON to Vapi)
      │
      │  HTTP 200 JSON: { "results": [{ "toolCallId": "...", "result": "..." }] }
      ▼
Vapi Voice Agent (reads result, continues conversation)
```

### 1.3 The Vapi Request Body Structure (Critical)

This is the most important thing to understand. Vapi does **not** send tool parameters at the root of the request body. They are nested inside `message.toolCallList[0].function.arguments`:

```json
{
  "message": {
    "toolCallList": [
      {
        "id": "call_abc123xyz",
        "function": {
          "name": "create_calendar_event",
          "arguments": {
            "title": "Meeting with Marco",
            "startDateTime": "2026-05-11T10:00:00+02:00",
            "endDateTime": "2026-05-11T11:00:00+02:00",
            "timezone": "Europe/Zurich"
          }
        }
      }
    ]
  }
}
```

> **The `toolCallId`** is at `message.toolCallList[0].id`.
> **The tool parameters** are at `message.toolCallList[0].function.arguments`.
>
> Accessing `body.title` or `body.limit` directly will always return `undefined`. You must dig into `arguments`.

Additionally, n8n may wrap the entire Vapi payload under a `body` key when received via the Webhook node (i.e., `$input.first().json.body` instead of `$input.first().json`). Always handle both cases.

---

## 2. Reading a Vapi Tool Definition

### 2.1 What to Extract

Given a Vapi Custom Tool JSON like this:

```json
{
  "type": "function",
  "function": {
    "name": "create_calendar_event",
    "description": "Creates an event in the personal calendar.",
    "parameters": {
      "type": "object",
      "properties": {
        "title":         { "type": "string",  "description": "Event title" },
        "startDateTime": { "type": "string",  "description": "Start (ISO 8601)" },
        "endDateTime":   { "type": "string",  "description": "End (ISO 8601)" },
        "timezone":      { "type": "string",  "description": "IANA timezone" },
        "participants":  { "type": "array",   "items": { "type": "string" } }
      },
      "required": ["title", "startDateTime", "endDateTime", "timezone"]
    }
  },
  "server": {
    "url": "https://n8n.example.com/webhook/7de457db-18c4-4276-8229-e975c95d33f4"
  }
}
```

Extract:

| Field | Where to find it | Used for |
|-------|-----------------|----------|
| **Webhook UUID** | Last path segment of `server.url` | Set as `path` and `webhookId` in Webhook node |
| **Required parameters** | `function.parameters.required` array | Validation throws in Code node |
| **Optional parameters** | All properties NOT in `required` | Default values in Code node |
| **Parameter types** | Each property's `type` field | Type coercion (arrays→strings for Gmail, strings→objects for Calendar attendees) |
| **Tool name** | `function.name` | Workflow name in n8n |

### 2.2 Webhook URL Convention

| Type | URL Pattern | When it responds |
|------|------------|-----------------|
| **Production** | `/webhook/<uuid>` | Only when workflow is **Active** (toggle ON) |
| **Test** | `/webhook-test/<uuid>` | Only while editor is open and listening |

**Vapi always calls the production URL.** Never use `/webhook-test/` in a Vapi tool's `server.url`.

---

## 3. Correct n8n Workflow Structure

Every Vapi-compatible n8n workflow must follow this exact 5-node linear pattern:

```
[Webhook] → [Validate Input] → [Action Node] → [Format Response] → [Respond to Vapi]
```

### Node 1 — Webhook

```json
{
  "parameters": {
    "httpMethod": "POST",
    "path": "<uuid-from-server.url>",
    "responseMode": "responseNode",
    "options": {}
  },
  "name": "Webhook",
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 2,
  "webhookId": "<uuid-from-server.url>"
}
```

**Critical settings:**
- `httpMethod` MUST be `"POST"` — Vapi always sends POST, never GET
- `responseMode` MUST be `"responseNode"` — delegates the HTTP response to the Respond to Webhook node
- `path` and `webhookId` must both be the exact UUID from `server.url`

### Node 2 — Code: Validate & Extract Parameters

This is the most critical code node. It must extract parameters from the correct Vapi nested path:

```javascript
const raw = $input.first().json;
const body = raw.body ?? raw;  // handle n8n body-wrapping

// Extract arguments from the correct Vapi nested path
const vapiArgs = body?.message?.toolCallList?.[0]?.function?.arguments
  ?? body?.toolCallList?.[0]?.function?.arguments
  ?? {};

// Fall back to body root for direct curl tests where params are at root level
const args = Object.keys(vapiArgs).length > 0 ? vapiArgs : body;

// Validate required parameters
if (!args.title)         throw new Error('title is required');
if (!args.startDateTime) throw new Error('startDateTime is required');

// Extract with defaults
const title         = args.title;
const startDateTime = args.startDateTime;
const timezone      = args.timezone ?? 'Europe/Zurich';

return [{ json: { title, startDateTime, timezone } }];
```

### Node 3 — Action Node (Gmail / Google Calendar / HTTP Request / etc.)

Configure the relevant n8n integration node using `={{ $json.fieldName }}` expressions referencing the output of Node 2.

### Node 4 — Code: Format Response (Vapi Envelope)

```javascript
// Get toolCallId from the original Webhook input (NOT $input — that's the action node output)
const rawW = $('Webhook').first().json;
const bW = rawW.body ?? rawW;
const toolCallId =
  bW?.message?.toolCallList?.[0]?.id
  ?? bW?.toolCallList?.[0]?.id
  ?? bW?.toolCallId
  ?? 'unknown';

// Build your result object from the action node output
const result = $input.first().json;
const data = {
  success: true,
  eventId: result.id ?? '',
  message: 'Evento creato con successo'
};

// Return the Vapi-compliant envelope — result MUST be a JSON string
return [{
  json: {
    results: [{
      toolCallId,
      result: JSON.stringify(data)
    }]
  }
}];
```

### Node 5 — Respond to Webhook

```json
{
  "parameters": {
    "respondWith": "json",
    "responseBody": "={{ JSON.stringify($json) }}",
    "options": { "responseCode": 200 }
  },
  "name": "Respond to Vapi",
  "type": "n8n-nodes-base.respondToWebhook",
  "typeVersion": 1
}
```

---

## 4. The Two Most Critical Patterns

### 4.1 Parameter Extraction (The #1 Source of Errors)

Always use this full extraction pattern in every Validate Input Code node:

```javascript
const raw = $input.first().json;
const body = raw.body ?? raw;

// PRIMARY: Vapi nested path
const vapiArgs = body?.message?.toolCallList?.[0]?.function?.arguments
  ?? body?.toolCallList?.[0]?.function?.arguments
  ?? {};

// FALLBACK: body root (for direct curl tests)
const args = Object.keys(vapiArgs).length > 0 ? vapiArgs : body;

// Access parameters via args.paramName — never via body.paramName directly
```

### 4.2 The Vapi Response Envelope (The #2 Source of Errors)

Vapi will show **"No result returned"** if the response format is wrong. The required format is:

```json
{
  "results": [
    {
      "toolCallId": "call_abc123xyz",
      "result": "{\"success\":true,\"eventId\":\"abc\",\"message\":\"Evento creato con successo\"}"
    }
  ]
}
```

| Rule | Correct | Wrong |
|------|---------|-------|
| Wrapper key | `results` (array) | `result`, `data`, `output`, plain object |
| `toolCallId` value | Mirror of what Vapi sent | Hardcoded, empty, or `"unknown"` |
| `result` field type | **JSON string** (use `JSON.stringify()`) | Object, number, array |
| toolCallId source node | `$('Webhook').first().json` | `$input.first().json` |
| HTTP status | `200` | `201`, `204`, `422` |

---

## 5. JSON Workflow Structure for Programmatic Generation

### 5.1 Minimal Valid Workflow JSON

```json
{
  "name": "workflow_name",
  "nodes": [ ],
  "connections": { },
  "active": true,
  "settings": { "executionOrder": "v1" },
  "tags": []
}
```

### 5.2 Connections Object (Must Be Unbroken Chain)

The `connections` object must form a complete unbroken chain from `"Webhook"` all the way to `"Respond to Vapi"`:

```json
{
  "connections": {
    "Webhook":          { "main": [[{ "node": "Validate Input",   "type": "main", "index": 0 }]] },
    "Validate Input":   { "main": [[{ "node": "Gmail - Send",     "type": "main", "index": 0 }]] },
    "Gmail - Send":     { "main": [[{ "node": "Format Response",  "type": "main", "index": 0 }]] },
    "Format Response":  { "main": [[{ "node": "Respond to Vapi",  "type": "main", "index": 0 }]] }
  }
}
```

> **Validation rule:** `"Respond to Vapi"` must appear as a `node` value inside `connections`. If it only exists in `nodes` but not in `connections`, n8n will throw "Unused Respond to Webhook node found in the workflow".

### 5.3 Node Naming Consistency

The `name` field in the `nodes` array must **exactly match** (case-sensitive, spaces included) the key used in `connections`:

```json
// In nodes array:
{ "name": "Gmail - Send", ... }

// In connections — must match character for character:
{ "Gmail - Send": { "main": [[...]] } }
```

### 5.4 Node Positions

Cosmetic but required. Use a simple horizontal layout:

```python
def pos(col): return [col * 300, 0]
# n1: [0,0], n2: [300,0], n3: [600,0], n4: [900,0], n5: [1200,0]
```

---

## 6. Node-Specific Implementation Patterns

### 6.1 Gmail Nodes

#### Send Email

```json
{
  "parameters": {
    "sendTo":  "={{ $json.to }}",
    "subject": "={{ $json.subject }}",
    "message": "={{ $json.bodyText }}",
    "options": {
      "ccList":  "={{ $json.cc }}",
      "bccList": "={{ $json.bcc }}"
    }
  },
  "type": "n8n-nodes-base.gmail",
  "typeVersion": 2.1
}
```

**Type coercion:** Vapi sends `to`, `cc`, `bcc` as arrays. Gmail expects comma-separated strings. Always convert in the Code node:

```javascript
const to  = Array.isArray(args.to)  ? args.to.join(',')  : args.to;
const cc  = Array.isArray(args.cc)  ? args.cc.join(',')  : (args.cc  ?? '');
const bcc = Array.isArray(args.bcc) ? args.bcc.join(',') : (args.bcc ?? '');
```

#### Get Messages (List Emails)

```json
{
  "parameters": {
    "resource":  "message",
    "operation": "getAll",
    "returnAll": false,
    "limit":     "={{ $json.limit }}",
    "filters":   { "q": "={{ $json.gmailQuery }}" },
    "options":   { "format": "resolved" }
  },
  "type": "n8n-nodes-base.gmail",
  "typeVersion": 2.1
}
```

**Use `format: resolved`** to get parsed headers (From, To, Subject, Date) instead of raw base64 MIME.

**`sinceDateTime` → Gmail `after:` filter:**
```javascript
if (args.sinceDateTime) {
  const ts = Math.floor(new Date(args.sinceDateTime).getTime() / 1000);
  gmailQuery += ' after:' + ts;
}
```

#### Reply to Email

```json
{
  "parameters": {
    "resource":  "message",
    "operation": "reply",
    "messageId": "={{ $json.messageId }}",
    "threadId":  "={{ $json.threadId }}",
    "message":   "={{ $json.bodyText }}",
    "options":   {}
  },
  "type": "n8n-nodes-base.gmail",
  "typeVersion": 2.1
}
```

### 6.2 Google Calendar Nodes

#### Create Event

```json
{
  "parameters": {
    "calendar": { "__rl": true, "value": "primary", "mode": "list", "cachedResultName": "primary" },
    "start": "={{ $json.startDateTime }}",
    "end":   "={{ $json.endDateTime }}",
    "additionalFields": {
      "summary":     "={{ $json.title }}",
      "description": "={{ $json.description }}",
      "location":    "={{ $json.location }}",
      "attendees":   "={{ $json.participants.map(e => ({email: e})) }}",
      "sendUpdates": "={{ $json.sendInvites ? 'all' : 'none' }}"
    }
  },
  "type": "n8n-nodes-base.googleCalendar",
  "typeVersion": 1.2
}
```

**Important:** `attendees` must be `[{ email: "..." }]` objects, not plain strings. Always map with `.map(e => ({email: e}))`.

#### Get Events (for availability check)

```json
{
  "parameters": {
    "resource":  "event",
    "operation": "getAll",
    "calendar":  { "__rl": true, "value": "primary", "mode": "list", "cachedResultName": "primary" },
    "returnAll": true,
    "options": {
      "timeMin":  "={{ $json.startDateTime }}",
      "timeMax":  "={{ $json.endDateTime }}",
      "timezone": "={{ $json.timezone }}"
    }
  },
  "type": "n8n-nodes-base.googleCalendar",
  "typeVersion": 1.2
}
```

---

## 7. Complete Error Catalogue

### Error 1: "title is required" / "[parameter] is required" — even though Vapi sent it

**Symptom:** n8n execution fails at Validate Input with a required-field error, even though the Vapi agent clearly sent the parameter value.

**Root cause:** The Code node accesses `body.title` or `args.title` where `args = body`, but Vapi stores tool parameters inside `body.message.toolCallList[0].function.arguments`. The parameter is present but at the wrong path.

**Fix:** Always extract `vapiArgs` from the nested Vapi path before accessing parameters:

```javascript
const vapiArgs = body?.message?.toolCallList?.[0]?.function?.arguments
  ?? body?.toolCallList?.[0]?.function?.arguments
  ?? {};
const args = Object.keys(vapiArgs).length > 0 ? vapiArgs : body;
// Then: args.title, args.startDateTime, etc.
```

---

### Error 2: "No result returned" in Vapi

**Symptom:** Vapi logs show the tool was called with a green checkmark, but the agent says "no emails found" or "appointment was created" even though nothing happened. Vapi dashboard shows "No result returned."

**Root cause:** The workflow returns a plain JSON object instead of the required `{ results: [{ toolCallId, result }] }` envelope. The `result` field is an object instead of a JSON string.

**Fix:** The Format Response Code node must build the envelope with `JSON.stringify()`:
```javascript
return [{json: {
  results: [{
    toolCallId,
    result: JSON.stringify(yourData)  // string, not object
  }]
}}];
```

---

### Error 3: "Unused Respond to Webhook node found in the workflow"

**Symptom:** curl POST returns `{"code":0,"message":"Unused Respond to Webhook node found in the workflow"}`. No action is performed.

**Root cause:** The `Respond to Webhook` node exists in `nodes` but is not reachable via `connections` — it is an orphaned/floating node.

**Fix:** Ensure `connections` contains a complete chain ending with `"Respond to Vapi"` as a target `node` value. Verify programmatically:

```python
assert "Respond to Vapi" in str(workflow["connections"])
```

In the n8n UI: confirm there is a visible arrow from the last Code node to the Respond to Vapi node.

---

### Error 4: 404 "This webhook is not registered for POST requests. Did you mean to make a GET request?"

**Symptom:** `curl -X POST ...webhook/<uuid>` returns 404.

**Root causes:**
1. Webhook node HTTP method is set to `GET` instead of `POST`
2. Workflow is not activated
3. Workflow was never saved after import

**Fix:**
1. Click Webhook node → change HTTP Method to `POST`
2. Toggle workflow to Active (green) → Save (Ctrl+S)

---

### Error 5: 404 "The requested webhook is not registered"

**Symptom:** curl returns 404 even with correct HTTP method.

**Root cause:** Workflow is not activated (`"active": true` in imported JSON is ignored — activation must be done manually in the UI after every import).

**Fix:** Open the workflow → flip the Active toggle → Save. The `active: true` flag in the JSON file does not automatically activate the workflow on import.

---

### Error 6: Workflow executes but action node fails silently (green but no email/event)

**Symptom:** n8n shows a green execution, Vapi gets a response, but Gmail didn't send / Calendar didn't create event.

**Root causes:**
- Credential field left as placeholder (`"GMAIL_CREDENTIAL_ID"`)
- OAuth token expired or revoked
- Wrong node `typeVersion`

**Fix:**
1. Click each action node → expand credential selector → choose real OAuth2 credential
2. Re-authenticate via Settings → Credentials if token is expired
3. Use `typeVersion: 2.1` for Gmail, `typeVersion: 1.2` for Google Calendar

---

### Error 7: `toolCallId` is `"unknown"` in response

**Symptom:** Response has `"toolCallId": "unknown"` — Vapi may behave erratically.

**Root cause:** The Format Response node uses `$input.first().json` to get the `toolCallId`, but at that stage `$input` is the Gmail/Calendar output, not the original Vapi request.

**Fix:** Always reference the Webhook node by name:
```javascript
// WRONG — $input here is the action node output
const toolCallId = $input.first().json?.message?.toolCallList?.[0]?.id;

// CORRECT — reference original request by node name
const rawW = $('Webhook').first().json;
const bW = rawW.body ?? rawW;
const toolCallId = bW?.message?.toolCallList?.[0]?.id ?? 'unknown';
```

---

### Error 8: No executions appear in n8n Executions tab

**Symptom:** Vapi calls the tool, no n8n executions logged.

**Root causes:**
1. Workflow is not activated
2. Vapi is calling the test URL (`/webhook-test/`) instead of the production URL (`/webhook/`)

**Fix:**
1. Activate the workflow (toggle ON + Save)
2. Verify Vapi `server.url` uses `/webhook/` not `/webhook-test/`
3. Test manually: `curl -X POST https://domain/webhook/<uuid> -H "Content-Type: application/json" -d '{}'` — if 404, the workflow is not active

---

### Error 9: Empty results from Gmail getAll

**Symptom:** Workflow runs successfully but returns `{ emails: [], count: 0 }` even though emails exist.

**Root causes:**
- `format` not set to `"resolved"` → headers not parsed
- Wrong `labelIds` filter format
- `limit` evaluates to `0`

**Fix:** Always use `"format": "resolved"` in Gmail getAll options. Use Gmail query string (`q`) instead of `labelIds` for filtering:
```json
"filters": { "q": "={{ $json.gmailQuery }}" },
"options": { "format": "resolved" }
```

---

### Error 10: Google Calendar "attendees" API error

**Symptom:** Create event fails with Google Calendar API error about attendees format.

**Root cause:** Vapi sends `participants` as `["email@example.com"]`. Google Calendar API requires `[{ "email": "email@example.com" }]`.

**Fix:** Always map in the expression:
```
={{ $json.participants.map(e => ({email: e})) }}
```

---

## 8. Workflow Generation Checklist

### Input Phase — Reading Vapi Tool Config
- [ ] Extract webhook UUID from `server.url` (last path segment)
- [ ] List all `required` parameters — will throw errors if missing
- [ ] List all optional parameters — will use defaults
- [ ] Note `array`-type parameters — need joining (Gmail) or `{email}` mapping (Calendar)
- [ ] Identify action type: Gmail / Calendar / HTTP Request / etc.

### JSON Generation Phase
- [ ] Webhook node: `httpMethod: "POST"`, `responseMode: "responseNode"`, `path` = UUID, `webhookId` = UUID
- [ ] Validate Code node: extracts `vapiArgs` from `body.message.toolCallList[0].function.arguments`
- [ ] Validate Code node: uses `Object.keys(vapiArgs).length > 0 ? vapiArgs : body` fallback
- [ ] Validate Code node: throws `Error` for each required missing field
- [ ] Action node: correct `typeVersion` (Gmail: `2.1`, Google Calendar: `1.2`)
- [ ] Format Response Code node: uses `$('Webhook').first().json` (NOT `$input`) for toolCallId
- [ ] Format Response Code node: full 6-path defensive toolCallId extraction
- [ ] Format Response Code node: `result` field is `JSON.stringify(data)` — string not object
- [ ] Format Response Code node: returns `{ results: [{ toolCallId, result }] }`
- [ ] Respond node: `respondWith: "json"`, `responseBody: "={{ JSON.stringify($json) }}"`, `responseCode: 200`
- [ ] `connections` object: unbroken chain Webhook → ... → Respond to Vapi
- [ ] `connections` verified: `"Respond to Vapi"` appears as a `node` value (not just in `nodes` array)
- [ ] Node names in `nodes` array exactly match (case + spaces) keys in `connections`
- [ ] Credential fields use placeholder IDs (replaced manually in n8n UI after import)

### Post-Import Phase — n8n UI
- [ ] All action nodes have real credentials assigned
- [ ] Workflow toggle set to **Active** (green)
- [ ] Workflow saved (Ctrl+S)
- [ ] Production URL confirmed: `/webhook/<uuid>` (NOT `/webhook-test/<uuid>`)
- [ ] curl POST test returns `{"results":[{"toolCallId":"test123","result":"..."}]}`
- [ ] n8n Executions tab shows a completed execution

---

## 9. Reference: Full Working Workflow Template

Copy-paste template for any Vapi Custom Tool workflow. Replace `<UUID>`, node names, action node parameters, and Format Response logic.

```json
{
  "name": "my_tool_name",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "<UUID-FROM-VAPI-SERVER-URL>",
        "responseMode": "responseNode",
        "options": {}
      },
      "id": "n1",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [0, 0],
      "webhookId": "<UUID-FROM-VAPI-SERVER-URL>"
    },
    {
      "parameters": {
        "jsCode": "const raw = $input.first().json;\nconst body = raw.body ?? raw;\nconst vapiArgs = body?.message?.toolCallList?.[0]?.function?.arguments ?? body?.toolCallList?.[0]?.function?.arguments ?? {};\nconst args = Object.keys(vapiArgs).length > 0 ? vapiArgs : body;\nif (!args.requiredParam) throw new Error('requiredParam is required');\nconst param1 = args.requiredParam;\nconst param2 = args.optionalParam ?? 'default';\nreturn [{ json: { param1, param2 } }];"
      },
      "id": "n2",
      "name": "Validate Input",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [300, 0]
    },
    {
      "parameters": {
        "...": "ACTION NODE PARAMETERS — reference $json.param1 etc."
      },
      "id": "n3",
      "name": "Action Node",
      "type": "n8n-nodes-base.<action>",
      "typeVersion": 1,
      "position": [600, 0],
      "credentials": {
        "credentialType": {
          "id": "REPLACE_WITH_REAL_CREDENTIAL_ID",
          "name": "My Credential"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "const rawW = $('Webhook').first().json;\nconst bW = rawW.body ?? rawW;\nconst toolCallId = bW?.message?.toolCallList?.[0]?.id ?? bW?.toolCallList?.[0]?.id ?? bW?.toolCallId ?? 'unknown';\nconst result = $input.first().json;\nconst data = { success: true, id: result.id ?? '', message: 'Completed successfully' };\nreturn [{ json: { results: [{ toolCallId, result: JSON.stringify(data) }] } }];"
      },
      "id": "n4",
      "name": "Format Response",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [900, 0]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "options": { "responseCode": 200 }
      },
      "id": "n5",
      "name": "Respond to Vapi",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1200, 0]
    }
  ],
  "connections": {
    "Webhook":       { "main": [[{ "node": "Validate Input",  "type": "main", "index": 0 }]] },
    "Validate Input":{ "main": [[{ "node": "Action Node",     "type": "main", "index": 0 }]] },
    "Action Node":   { "main": [[{ "node": "Format Response", "type": "main", "index": 0 }]] },
    "Format Response":{ "main": [[{ "node": "Respond to Vapi","type": "main", "index": 0 }]] }
  },
  "active": true,
  "settings": { "executionOrder": "v1" },
  "tags": []
}
```

---

## 10. Testing Protocol

### Step 1: curl Smoke Test — Simulating a Real Vapi Call

To properly simulate what Vapi sends, include the `message.toolCallList` structure with `function.arguments`:

```bash
curl -X POST https://<n8n-domain>/webhook/<uuid> \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "toolCallList": [{
        "id": "test_call_001",
        "function": {
          "name": "create_calendar_event",
          "arguments": {
            "title": "Test Meeting",
            "startDateTime": "2026-05-12T10:00:00+02:00",
            "endDateTime": "2026-05-12T11:00:00+02:00",
            "timezone": "Europe/Zurich"
          }
        }
      }]
    }
  }'
```

**Expected response:**
```json
{
  "results": [
    {
      "toolCallId": "test_call_001",
      "result": "{\"success\":true,\"eventId\":\"abc123\",\"message\":\"Evento creato con successo\"}"
    }
  ]
}
```

### Step 2: Failure Response Lookup Table

| Response | Meaning | Fix |
|----------|---------|-----|
| `404 webhook not registered for POST` | Webhook node set to GET | Change to POST, save, reactivate |
| `404 webhook not registered` | Workflow inactive | Activate toggle + Save |
| `{"code":0,"message":"Unused Respond to Webhook..."}` | Respond node not wired in connections | Fix connections chain |
| `{"results":[{"toolCallId":"unknown",...}]}` | toolCallId extraction failed | Use `$('Webhook').first().json` |
| `{"results":[{"toolCallId":"...","result":"{}"}]}` | Action node silently failed | Check credentials, check Executions tab |
| `500` or action node error | API error or bad params | Check Executions tab → click failed node |
| Empty `emails: []` from Gmail | Wrong query or missing `format:resolved` | Add `"format": "resolved"` to Gmail options |

### Step 3: n8n Executions Tab Check

After a successful curl, open n8n → **Executions tab** (left sidebar) → confirm a green execution appears. Click it to inspect each node's input/output and verify parameters flowed correctly through all nodes.

### Step 4: Vapi Live Test

Make a voice call to the Vapi agent and trigger the tool verbally. Check:
- Vapi tool call log shows HTTP `200`
- Vapi tool result shows the `results` envelope (not "No result returned")
- The actual action occurred (email sent, calendar event visible, etc.)

---

## 11. Quick Reference Summary

| Aspect | Correct value |
|--------|--------------|
| Webhook HTTP method | `POST` |
| Webhook responseMode | `responseNode` |
| Webhook path | UUID from `server.url` (no slashes, no prefix) |
| Tool parameters location in Vapi body | `message.toolCallList[0].function.arguments` |
| Parameter extraction variable | `args` (from vapiArgs with body fallback) |
| Vapi response root key | `results` (array) |
| Vapi `result` field type | JSON **string** — use `JSON.stringify()` |
| toolCallId location | `message.toolCallList[0].id` |
| toolCallId source node in n8n | `$('Webhook').first().json` (not `$input`) |
| n8n body wrapping | Use `raw.body ?? raw` everywhere |
| Gmail typeVersion | `2.1` |
| Google Calendar typeVersion | `1.2` |
| Calendar attendees format | `[{ email: "..." }]` objects, not strings |
| Gmail `to`/`cc`/`bcc` format | Comma-separated string (join arrays) |
| Activation after import | **Manual toggle in UI — `active:true` in JSON is ignored** |
| Production URL pattern | `/webhook/<uuid>` (NOT `/webhook-test/<uuid>`) |
| Connections must include | `"Respond to Vapi"` as a `node` target value |
| curl test body structure | Must include `message.toolCallList[0].function.arguments` to simulate real Vapi call |
