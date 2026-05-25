# `/vapi-build` — User Guide

Welcome. This skill turns a one-line idea ("a receptionist that books meetings and sends confirmation emails") into a production-grade Vapi voice agent — phone number, custom tools, n8n workflows, and all — without you ever leaving the chat.

---

## 1. What it does

`/vapi-build` is an **interactive factory** for Vapi voice agents. It drives you through a numbered menu and:

1. Verifies your Vapi CLI install + login.
2. Creates the assistant on Vapi (model, voice, transcriber, system prompt, first message).
3. For every custom tool you describe, it generates and **publishes** a matching n8n workflow — strictly following the production-tested Vapi↔n8n contract (Production URL only, correct envelope, defensive parameter extraction).
4. Wires each n8n production webhook into the assistant's `tools` array.
5. Attaches a phone number (existing, new, or skip for web-only).
6. Smoke-tests every tool with a real curl before declaring success.
7. Saves every artifact (assistant JSON, tool JSONs, workflow JSONs, build summary) under `./vapi-build-out/<agent-slug>/`.

---

## 2. How to invoke

Any of these works:

- Type `/vapi-build`
- Say `VAPI GO` or `vapi go` (case-insensitive, can be embedded mid-sentence)
- Ask Claude something like "build me a Vapi receptionist" — the skill auto-triggers

Once invoked, you'll see the **Main Menu**. Reply with a number.

```
1) 🆕  Create a NEW voice agent (full guided flow)
2) 🛠️   Add custom tools to an EXISTING agent
3) 🔧  Update an existing agent
4) 📞  Manage phone numbers
5) 🧪  Test an agent
6) 🔌  Setup / verify Vapi CLI
7) 📚  Show this user documentation
0) Exit
```

---

## 3. Prerequisites

| Requirement | How to satisfy |
|---|---|
| Vapi CLI installed | The skill auto-installs via `curl -sSL https://vapi.ai/install.sh \| bash` if missing. |
| Vapi account + login | The skill runs `vapi login` for you. |
| n8n instance | Self-hosted or cloud. You'll provide the **base URL** + an **API key** the first time. Alternatively, an n8n MCP server connected to Claude Code is auto-detected and used. |
| LLM / TTS / STT keys | Configured **inside Vapi** (dashboard → Keys). The skill assumes they exist. |
| Credentials inside n8n | Gmail, Google Calendar, DB credentials must be pre-configured in n8n → Credentials. The skill will pause and tell you when to assign them. |

---

## 4. Walking through Flow 1 (Create a NEW agent)

The flow is staged. After every stage the skill **summarises what's about to happen and waits for your `ok`** before doing irreversible things.

| Stage | What happens | What you'll be asked |
|---|---|---|
| 1.1 Identity | Name + language + persona blurb | "What does this agent do, in 1–3 sentences?" |
| 1.2 Voice stack | Curated bundles (Premium EN/IT/Fast/Custom) | Pick a letter |
| 1.3 Prompt expansion | Skill turns the blurb into a full system prompt | Edit / approve |
| 1.4 Custom tools | Loop per tool — see §5 below | Tool name, description, parameters, action type |
| 1.5 Assemble | Builds `assistant.json`, runs `vapi assistant create` | `ok` to submit |
| 1.6 Phone | List / buy / skip | Pick a number |
| 1.7 Smoke test | Live `vapi logs` + a test call | Place call, report result |
| 1.8 Save | Writes `BUILD_SUMMARY.md` | (nothing — just done) |

---

## 5. The custom-tool sub-flow (the real superpower)

For each tool you describe, the skill executes 8 micro-steps automatically:

1. **Collect spec** — name, description, parameters (with type & required flag), action type.
2. **Generate Vapi tool JSON** — saved to `tools/<name>.vapi.json`.
3. **Mint a UUID** — used as both n8n webhook `path` and `webhookId`.
4. **Generate n8n workflow JSON** — 5-node Vapi-compliant chain (Webhook → Validate → Action → Format Response → Respond to Vapi). Defensive parameter extraction. Type coercion (arrays→csv for Gmail, arrays→`[{email}]` for Calendar). Correct envelope with `JSON.stringify(result)`.
5. **Push to n8n** — via n8n MCP if available, otherwise via REST API + `/activate`. Manual import only as a last resort.
6. **Pause for credentials** — if the action needs Gmail/Calendar/DB auth, the skill stops and tells you exactly which dropdown to set. Reply `done` to resume.
7. **Smoke test the Production URL** — runs a curl that exactly mirrors what Vapi will send (`message.toolCallList[0].function.arguments`). Won't proceed until it gets a 200 with the correct envelope.
8. **Wire the URL into the Vapi tool JSON** and append it to `BUILD_SUMMARY.md`.

> 🔒 **Production URL only.** The skill will *never* set a `server.url` to a `/webhook-test/` URL. Vapi only ever calls production endpoints.
> 🔒 **Active or it's not done.** A workflow that imports cleanly but isn't toggled Active is a silent failure waiting to happen. The skill activates via API and verifies before continuing.

---

## 6. Output you can re-run, audit, or hand off

```
./vapi-build-out/<agent-slug>/
├── assistant.json
├── tools/
│   ├── create_calendar_event.vapi.json
│   ├── create_calendar_event.n8n.json
│   ├── send_confirmation_email.vapi.json
│   └── send_confirmation_email.n8n.json
├── .state.json          # ids: assistantId, phoneNumberId, n8nWorkflowIds
└── BUILD_SUMMARY.md     # human-readable handoff
```

You can `vapi assistant update <id> --file ./vapi-build-out/.../assistant.json` any time to push changes, or re-import the n8n workflow JSONs to a new instance.

---

## 7. Common questions

**Q. Do I need to know JSON / n8n internals?**
No. You describe the tool in plain English; the skill writes the JSON.

**Q. What if my n8n is private (no public URL)?**
n8n itself must be reachable from Vapi's servers (so Vapi can POST to the production webhook). Use a tunnel (Cloudflare Tunnel, ngrok) or a public n8n cloud instance.

**Q. The agent calls the tool but says "no result"?**
That's almost always the response envelope. The skill's smoke test is designed to catch this before the call ever happens. If it slips through, jump to Menu 5 and we'll re-run the curl + diff.

**Q. Can I edit a tool later?**
Yes — Menu 2 (add tools) and re-running Menu 1 with the same agent slug will diff and patch. To change parameter shape, edit the n8n workflow's Validate Input node + the Vapi tool JSON, then `vapi assistant update`.

**Q. How are secrets handled?**
The skill never writes API keys to disk. Vapi keys live in `vapi auth`. n8n keys are read from your environment (`N8N_API_KEY`) or asked once per session and held in memory only.

---

## 8. Troubleshooting cheatsheet

| Symptom | First thing to check |
|---|---|
| `vapi: command not found` | Menu 6 → reinstall |
| Tool call lands but conversation hangs | Smoke test the URL again — envelope or `JSON.stringify` issue |
| `"toolCallId":"unknown"` in response | Format Response node used `$input` instead of `$('Webhook')` |
| 404 from production webhook | Workflow not Active — re-activate via API |
| n8n executes but Gmail/Calendar didn't act | Credential placeholder still in node — assign in n8n UI |
| Vapi shows "no result returned" | Wrong envelope — `result` must be a JSON string, not an object |

For the full error catalogue see `references/n8n-workflow-guide.md` §7.

---

## 9. Philosophy

- **Always interactive, never silent.** The skill explains each step before doing it.
- **Production-first.** No test webhooks, no half-active workflows, no hardcoded toolCallIds.
- **Verify before declaring done.** Every tool earns its place by passing a curl smoke test first.
- **Save everything.** Your `vapi-build-out/` directory is the source of truth — re-runnable, auditable, gift-wrappable.

Happy building. 🎙️
