---
description: Interactive builder for immersive scroll-driven hero websites via Gemini API (Nano Banana + Veo 3.1 → 1920×1005 frames → Antigravity)
---

Invoke the `magic-web` skill via the Skill tool. The skill drives the full guided menu: auth choice (Google AI Studio key vs Vertex AI), image-model choice (Nano Banana 2 vs Nano Banana Pro), video-model choice (Veo 3.1 Fast vs Veo 3.1 Lite, always 1080p), cost confirmation, topic & parameters, 4-prompt architecture, dual image generation, video generation, ffmpeg crop (75 px bottom → 1920×1005) + 30 fps normalize, full frame extraction, and Antigravity-CLI website generation.

If the user passed arguments after `/magic-web`, treat them as the topic description and route directly to Flow 1 → Stage 0 with that topic pre-filled. Otherwise, print the welcome banner and Main Menu and wait for the user to pick.
