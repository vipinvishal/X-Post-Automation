#!/usr/bin/env python3
"""
infographic.py — Turn the day's research into a branded hand-drawn-style
infographic PNG, then host it so Buffer can attach it to the Threads post.

Pipeline (called from generate_and_schedule.py):
    research brief  ->  content JSON (reuses the Gemini/Euron text chain)
                    ->  renderer/render.py  (Playwright -> 1800px PNG)
                    ->  imgbb  (public URL for Buffer's assets[].image.url)

The renderer is the proven system from Auto_infographics_system (Jinja2 template
+ embedded handwriting fonts + portrait). We only swap "email the PNG" for
"upload it and return a public URL".
"""

import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import requests

# ── Paths ───────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT  = _SCRIPT_DIR.parent
_RENDERER   = _REPO_ROOT / "renderer"
_RENDER_PY  = _RENDERER / "render.py"

# ── Config ──────────────────────────────────────────────────────────────────────
# Handle shown on the infographic. Change to your brand without touching code,
# e.g. INFOGRAPHIC_HANDLE="@orbitailabs".
INFOGRAPHIC_HANDLE = os.environ.get("INFOGRAPHIC_HANDLE", "@VipinAIHub")
IMGBB_API_KEY      = os.environ.get("IMGBB_API_KEY", "")

# Icons the renderer ships with (renderer/icons.py).
ICON_NAMES = [
    "cloud", "copies", "database", "file", "gear",
    "key", "laptop", "lock", "network", "search", "upload",
]

# ── Content prompt (adapted from Auto_infographics_system/content_api.py) ────────
_SYSTEM = """You are an AI/Tech educator who designs single-image explainer infographics.
You take fresh AI / Generative-AI / Agentic-AI research and reframe it into ONE
evergreen "how it works" concept that can be explained in exactly 3 visual stages.
You ONLY cover Artificial Intelligence, Generative AI, AI tools, or Agentic AI.
Write ALL text in ENGLISH ONLY. You return valid JSON only: no markdown, no prose."""

_USER_TEMPLATE = """FRESH RESEARCH (last 48h, your inspiration — not the literal subject):
Topic: "{topic}"

SOURCES / CONTEXT:
{research}

---

TASK
Reframe this into ONE evergreen, teachable AI concept that fits a 3-stage
"how it works" infographic. Prefer the underlying mechanism over the news headline
(e.g. a story about a new agent framework -> "How an AI Agent Decides Its Next Action").

HARD RULES
- Topic MUST be about AI, Generative AI, AI tools, or Agentic AI. Nothing else.
- EXACTLY 3 stages and EXACTLY 3 explainers.
- Every value concrete and specific — no filler like "AI is powerful".
- stage.title <= 22 characters. stage.subtitle <= 30 characters, one line.
- stage.icon MUST be one of: {icons}
- arrow_note is a tiny 1-3 word label; the LAST stage's arrow_note MUST be "".
- explainer.body may use <span class='k1'>..</span>, <span class='k2'>..</span>,
  <span class='k3'>..</span> to highlight a key term, and <b>..</b> for bold.
- quote_main may use <span class='n'>NUMBER</span> and <span class='h'>highlight</span>.
- handle MUST be exactly "{handle}".
- terminal_cmd is a short, real-looking shell/CLI line, <= 18 chars, ideally
  one token (e.g. "agent.run()", "rag.query()"). No long arguments.
- sticky1 and sticky2 are <= 7 words each.

Return a single JSON object with EXACTLY these keys:
{{
  "topic": "the evergreen concept title, plain text",
  "headline_line1_pre": "text before the highlighted word, e.g. 'How '",
  "headline_line1_hl": "the ONE highlighted word, e.g. 'RAG'",
  "headline_line1_post": "text after it on line 1 (may be empty)",
  "headline_line2": "the second headline line (blue)",
  "sub_pre": "short lead, e.g. 'A Query Travels Through'",
  "sub_num": "3",
  "sub_post": "e.g. 'Stages'",
  "stages": [
    {{"title": "<=22 chars", "subtitle": "<=30 chars", "icon": "one of the icons", "arrow_note": "1-3 words"}},
    {{"title": "<=22 chars", "subtitle": "<=30 chars", "icon": "one of the icons", "arrow_note": "1-3 words"}},
    {{"title": "<=22 chars", "subtitle": "<=30 chars", "icon": "one of the icons", "arrow_note": ""}}
  ],
  "explainers": [
    {{"tag": "short heading", "body": "1-2 sentences, may use <span class='k1'> and <b>"}},
    {{"tag": "short heading", "body": "1-2 sentences, may use <span class='k2'> and <b>"}},
    {{"tag": "short heading", "body": "1-2 sentences, may use <span class='k3'> and <b>"}}
  ],
  "sticky1": "short aha note, use <b> for the key word",
  "terminal_cmd": "short CLI command",
  "sticky2": "short aha note, use <b> for the key word",
  "quote_main": "a punchy fact, use <span class='n'> for a number and <span class='h'> for highlight",
  "quote_sub": "one supporting line",
  "handle": "{handle}"
}}"""

_REQUIRED_KEYS = [
    "topic", "headline_line1_pre", "headline_line1_hl", "headline_line1_post",
    "headline_line2", "sub_pre", "sub_num", "sub_post", "stages", "explainers",
    "sticky1", "terminal_cmd", "sticky2", "quote_main", "quote_sub", "handle",
]


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    # Be forgiving if the model adds prose around the object.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


def _coerce(data: dict) -> dict:
    """Fix structural issues so render.py never crashes."""
    stages = data.get("stages") or []
    while len(stages) < 3:
        stages.append({"title": "", "subtitle": "", "icon": "file", "arrow_note": ""})
    stages = stages[:3]
    for i, st in enumerate(stages):
        st.setdefault("title", "")
        st.setdefault("subtitle", "")
        icon = st.get("icon", "file")
        st["icon"] = icon if icon in ICON_NAMES else "file"
        st["arrow_note"] = "" if i == 2 else st.get("arrow_note", "")
    data["stages"] = stages

    exps = data.get("explainers") or []
    while len(exps) < 3:
        exps.append({"tag": "", "body": ""})
    for ex in exps:
        ex.setdefault("tag", "")
        ex.setdefault("body", "")
    data["explainers"] = exps[:3]

    data["sub_num"] = str(data.get("sub_num", "3"))
    data["handle"] = INFOGRAPHIC_HANDLE
    for key in _REQUIRED_KEYS:
        data.setdefault(key, "")
    return data


def generate_infographic_content(research: str, topic: str, generate_text_fn) -> dict:
    """Build validated infographic content JSON, reusing the text-gen chain.

    generate_text_fn(prompt, system) -> str   (the Gemini/Euron chain from main)
    """
    prompt = _USER_TEMPLATE.format(
        topic=topic,
        research=(research or "").strip()[:5500] or topic,
        icons=", ".join(ICON_NAMES),
        handle=INFOGRAPHIC_HANDLE,
    )
    last_err = ""
    for attempt in range(1, 3):  # one retry
        user = prompt if attempt == 1 else prompt + f"\n\nPREVIOUS ATTEMPT FAILED: {last_err}\nReturn corrected JSON only."
        raw = generate_text_fn(user, _SYSTEM)
        try:
            data = _coerce(_parse_json(raw))
            print(f"  [Infographic] Content ready — topic: {data.get('topic', '?')}")
            return data
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            print(f"  [Infographic] Content parse failed (attempt {attempt}): {last_err}")
    raise RuntimeError(f"Infographic content generation failed: {last_err}")


def render_infographic(content: dict, out_path: str) -> str:
    """Render the content JSON to a PNG via renderer/render.py (Playwright)."""
    print("  [Infographic] Rendering PNG with Playwright...")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(content, fh)
        content_path = fh.name
    try:
        subprocess.run(
            [sys.executable, str(_RENDER_PY), content_path, out_path],
            check=True, cwd=str(_RENDERER),
        )
    finally:
        os.unlink(content_path)
    print(f"  [Infographic] Rendered -> {out_path}")
    return out_path


def upload_to_imgbb(png_path: str) -> str:
    """Upload the PNG to imgbb and return a public direct URL for Buffer."""
    if not IMGBB_API_KEY:
        raise RuntimeError("IMGBB_API_KEY not set — cannot host the infographic.")
    print("  [Infographic] Uploading to imgbb...")
    with open(png_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        params={"key": IMGBB_API_KEY},
        data={"image": b64},
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"imgbb upload {resp.status_code}: {resp.text[:300]}")
    url = resp.json()["data"]["url"]
    print(f"  [Infographic] Hosted at: {url}")
    return url
