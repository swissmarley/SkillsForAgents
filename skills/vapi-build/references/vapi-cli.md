# Vapi CLI Reference

Master sheet for `/vapi-build`. Source: https://docs.vapi.ai/cli (verified 2026-05).

## Install

```bash
# macOS / Linux
curl -sSL https://vapi.ai/install.sh | bash

# Windows (PowerShell)
iex ((New-Object System.Net.WebClient).DownloadString('https://vapi.ai/install.ps1'))

# Docker
docker run -it ghcr.io/vapiai/cli:latest --help
```

Verify:
```bash
vapi --version
vapi update check
```

## Auth

```bash
vapi login                  # OAuth flow, opens browser
vapi auth status            # who am I, list orgs
vapi auth switch <account>  # change org
vapi auth login             # add another org/account
```

API key fallback (CI / non-interactive):
```bash
export VAPI_API_KEY=<key>
```

## Project init

```bash
vapi init   # auto-detects framework (Next.js, Vue, Python, Go, Flutter, RN, …)
```

Use this only inside a user app project — irrelevant for our build flow.

## Assistants

```bash
vapi assistant list
vapi assistant create                       # interactive wizard
vapi assistant create --file ./assistant.json
vapi assistant get <id>
vapi assistant get <id> --output assistant.json
vapi assistant update <id> --file ./assistant.json
vapi assistant delete <id>
```

Minimum viable assistant JSON (the shape we build in Stage 1.5):

```json
{
  "name": "Receptionist Pro",
  "model": {
    "provider": "openai",
    "model": "gpt-4o",
    "messages": [
      { "role": "system", "content": "<expanded system prompt>" }
    ],
    "temperature": 0.4,
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "create_calendar_event",
          "description": "Creates a calendar event when the caller books a meeting.",
          "parameters": {
            "type": "object",
            "properties": {
              "title":         { "type": "string" },
              "startDateTime": { "type": "string" },
              "endDateTime":   { "type": "string" },
              "timezone":      { "type": "string" }
            },
            "required": ["title", "startDateTime", "endDateTime", "timezone"]
          }
        },
        "server": {
          "url": "https://n8n.example.com/webhook/<UUID>"
        }
      }
    ]
  },
  "voice": {
    "provider": "11labs",
    "voiceId": "rachel"
  },
  "transcriber": {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "en"
  },
  "firstMessage": "Hi, this is Ava — how can I help you today?",
  "endCallFunctionEnabled": true,
  "recordingEnabled": true
}
```

## Phone numbers

```bash
vapi phone list
vapi phone create                # interactive — pick country/area code
vapi phone update <id>           # set assistantId / fallback
vapi phone delete <id>
```

To attach an assistant to a number, run `vapi phone update <phoneId>` and set `assistantId: <assistantId>`.

## Calls

```bash
vapi call list
vapi call create                 # outbound test call
vapi call get <id>
vapi call end <id>
```

## Logs

```bash
vapi logs list
vapi logs calls <id>
vapi logs calls --tail            # live stream — useful while smoke testing
vapi logs errors
vapi logs webhooks                # confirms tool calls reached your n8n webhook
```

## Local dev / tunneling

```bash
vapi listen --forward-to localhost:3000/webhook
# pair with ngrok if you need a public URL for non-n8n tools
```

## MCP

```bash
vapi mcp setup     # registers Vapi MCP into Cursor / Windsurf / VSCode
```

## Config

```bash
vapi config get
vapi config set <key> <value>
vapi config analytics disable
```

## Update

```bash
vapi update check
vapi update
```

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `vapi: command not found` | install script didn't add to PATH | `source ~/.zshrc` or restart shell |
| `unauthorized` on every command | not logged in / token expired | `vapi login` |
| `assistant create` rejects tools | `server.url` missing or wrong shape | each tool needs `server.url` at the function level |
| Phone number rings but no agent | phone not linked | `vapi phone update <id>` with assistantId |
| Tool fires but conversation hangs | n8n returned wrong envelope | see `n8n-workflow-guide.md` §4.2 |
