#!/usr/bin/env python3
"""
X Post Agent
Pipeline: Exa (research) → Gemini (generate viral post) → Buffer (schedule to X)

Run locally : python scripts/generate_and_schedule.py
GitHub Actions triggers this automatically every day at 9 AM IST.
"""

import os
import json
import random
import time
import requests
from datetime import datetime, timezone, timedelta
from exa_py import Exa
from google import genai
from google.genai import types
from dotenv import load_dotenv

import infographic

# ── Load env (local dev; GitHub Actions injects env vars directly) ────────────
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY")
GEMINI_API_KEY_2  = os.environ.get("GEMINI_API_KEY_2")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY")
EURON_API_KEY     = os.environ.get("EURON_API_KEY")
EXA_API_KEY       = os.environ.get("EXA_API_KEY")
BUFFER_API_KEY    = os.environ.get("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.environ.get("BUFFER_CHANNEL_ID")

# ── Infographic image ─────────────────────────────────────────────────────────
# When on, single posts get a rendered infographic PNG attached via Buffer.
# Set INCLUDE_INFOGRAPHIC=0 to fall back to text-only (e.g. if imgbb key is missing).
# Threads (multi-tweet) are always text-only — images don't attach to threads.
INCLUDE_INFOGRAPHIC = os.environ.get("INCLUDE_INFOGRAPHIC", "1") not in ("0", "false", "False", "")

# Portfolio URL appended to the last tweet of every thread (not single posts —
# X suppresses text posts that contain external links in feeds).
PORTFOLIO_URL = os.environ.get("PORTFOLIO_URL", "https://vipin-vishal.onrender.com")

GEMINI_MODEL           = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-001"]
MAX_RETRIES            = 4
RETRY_BASE_SECONDS     = 15

# ── Load topics config ────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_script_dir, "topics.json"), "r") as f:
    _config = json.load(f)

NICHE         = _config["niche"]
PERSONA       = _config["persona"]
TOPICS        = _config["topics"]
SERIES_TOPICS = _config.get("series_topics", {})
TONES         = _config["tones"]

# Day-of-week series routing (0=Mon, 2=Wed, 4=Fri)
_SERIES_DAY_MAP = {
    0: "How It Actually Works",
    2: "Paper Breakdown",
    4: "Build and Learn",
}

# ── Hashtag selection ─────────────────────────────────────────────────────────
# X's character limit is 280. X counts any URL as exactly 23 chars (t.co).
# Budget: 280 - 25 (URL + \n\n) - 32 (hashtags + \n\n) = 223 → use 220 with margin.
_BODY_CHAR_LIMIT  = 220
_URL_TCOLEN       = 23   # X wraps all URLs to t.co links, always 23 chars

_HASHTAG_RULES = [
    (("transformer", "attention", "self-attention", "multi-head"),     "#Transformers #MachineLearning"),
    (("rag", "retrieval", "vector", "embedding", "chunk", "semantic"), "#RAG #LLM"),
    (("agent", "agentic", "tool call", "function call", "autonomous"), "#AgenticAI #LLM"),
    (("fine-tun", "finetun", "rlhf", "dpo", "lora", "train"),         "#LLMTraining #MachineLearning"),
    (("diffusion", "image generation", "denoising"),                   "#GenerativeAI #MachineLearning"),
    (("kv cache", "speculative", "quantiz", "inference", "latency"),   "#LLMOps #MachineLearning"),
    (("moe", "mixture of experts", "architecture", "layer"),           "#DeepLearning #MachineLearning"),
    (("context", "tokeniz", "token", "prompt", "temperature"),         "#LLM #MachineLearning"),
]
_DEFAULT_HASHTAGS = "#AI #MachineLearning"

# ── Content styles ─────────────────────────────────────────────────────────────
# Two post structures that alternate each run (9AM / 1PM / 7PM IST).
# Style 0: Problem → Solution   |   Style 1: Scenario → Risk → Solution
# The same style index is passed to the infographic so image and text are aligned.

_STYLE_LABELS = ["Problem → Solution", "Scenario → Risk → Solution"]

_STYLE_SINGLE_SECTION = [
    # Style 0 ── Problem → Solution
    """\
━━━ CONTENT STYLE 1: Problem → Solution ━━━
Write the post using this exact structure (total ≤ 220 chars — compress ruthlessly):
1. Open with the problem — something that confused you or tripped you up in AI/ML
2. Deepen it — why it's sneakier or more common than you'd expect
3. Walk through what you tried or what most people try (briefly)
4. The AI/ML concept as what actually works + the one mechanism that made it click for you
5. Close with a thought that reframes the reader's mental model from your learning
6. End with: "follow for one AI/ML deep dive per day"

Voice: you're sharing what you figured out, not teaching from authority.
"I got this wrong for a while." "here's what finally made it click." "TIL that..."\
""",
    # Style 1 ── Scenario → Risk → Solution
    """\
━━━ CONTENT STYLE 2: Scenario → Risk → Solution ━━━
Write the post using this exact structure (total ≤ 220 chars — compress ruthlessly):
1. Open with a vivid imaginary scenario — someone building an AI system hits a wall
2. Show what's at stake when you're actually shipping: what breaks, what the cost is
3. The security or failure risk this exposes (hallucination in prod, prompt injection, data leakage, cost blowup)
4. The AI/ML concept that addresses it + one concrete thing it does differently
5. Close with a question to spark discussion — "what's your experience with this?" or similar

Voice: you're the engineer who ran into this, not the expert with the answer.
"anyone else hit this?" "this one caught me off guard."\
""",
]

_STYLE_THREAD_SECTION = [
    # Style 0 ── Problem → Solution (6 tweets)
    """\
━━━ THREAD STYLE 1: Problem → Solution ━━━
Tweet 1 (HOOK): Open with the problem — something you got confused by or that broke for you. First-person. Max 150 chars. End with "→" or ":"
  Examples: "got this completely wrong for months. here's what attention actually computes →"
            "spent hours debugging why my RAG kept failing. the culprit surprised me:"
Tweet 2: Deepen the problem — why it's trickier than expected, what you tried first, how widespread it is
Tweet 3: What most people try (and why it doesn't fully solve it) — be honest, not condescending
Tweet 4: The AI/ML concept as the actual fix. Name it directly. Share the moment it clicked.
Tweet 5: The key mechanism — the one technical detail that made the concept finally make sense. Precise.
Tweet 6 (CLOSE): A thought that reframes how the reader sees this + "follow for one AI/ML deep dive per day." Include: {portfolio_url}\
""",
    # Style 1 ── Scenario → Risk → Solution (6 tweets)
    """\
━━━ THREAD STYLE 2: Scenario → Risk → Solution ━━━
Tweet 1 (HOOK): An imaginary scenario — someone building with AI runs into something unexpected. Max 150 chars. End with "→" or ":"
  Examples: "imagine you ship a RAG pipeline. users start getting confidently wrong answers. here's why →"
            "picture this: your AI agent starts leaking data between user sessions:"
Tweet 2: Why this matters when you're actually building — the real cost, failure mode, or blast radius
Tweet 3: The specific security or failure risk (be precise: hallucination, prompt injection, data leakage, latency cliff)
Tweet 4: The AI/ML concept that addresses it. Name it. Show you're learning it too, not presenting it as settled.
Tweet 5: How it works — 3 concrete mechanisms (numbered: 1. 2. 3.). Technical, not generic.
Tweet 6 (CLOSE): "this shifted how I think about [X] because [reason]" + "what's your take? drop it in the comments." Include: {portfolio_url}\
""",
]

_STYLE_INFOGRAPHIC_FRAMING = [
    "Problem → Root Cause → Solution Mechanism",  # Style 0
    "The Scenario → The Risk → The Fix",          # Style 1
]


def _pick_style_index() -> int:
    """Alternate style 0 / style 1 on every run (3 runs/day).
    Formula: (day_of_year × 3 + time_slot) % 2 → clean 0,1,0,1 alternation."""
    now  = datetime.now(timezone.utc)
    slot = 0 if now.hour < 6 else (1 if now.hour < 11 else 2)
    return (now.timetuple().tm_yday * 3 + slot) % 2


def _pick_hashtags(post_text: str, topic: str) -> str:
    combined = (post_text + " " + topic).lower()
    for keywords, tags in _HASHTAG_RULES:
        if any(k in combined for k in keywords):
            return tags
    return _DEFAULT_HASHTAGS


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You write X posts for an engineer who studies AI/ML every day and explains how it actually works under the hood. Not a founder, not a CEO, not an "AI tools" account. Just an engineer who reads the papers, runs experiments, and shares real mental models — learning in public, one concept at a time.

Voice: a smart engineer explaining something to another engineer. Clear, precise, a little informal. No hype. You respect the reader's intelligence but never assume they already know the concept.

Every post teaches one AI/ML concept with real technical depth — the kind of "oh, THAT'S how it works" insight people save. Correct, specific, genuinely educational. Never surface-level.

Examples of the exact voice and depth:

"quick one on why LLMs are bad at math. they don't see numbers. they see tokens. '1234' might split into '12' and '34'. so it's pattern-matching over token fragments, not reasoning over values. it was never doing arithmetic. it was doing text."

"the KV cache is why chat feels fast. without it, generating token 500 means recomputing attention for all 499 previous tokens every single step. the cache stores those key/value vectors so each new token only computes its own. O(n²) → O(n). that's the whole trick."

"fine-tuning doesn't teach new facts. it shifts the output distribution toward a style or format. if you want the model to know new information, you need RAG. confusing these leads to expensive mistakes."

"temperature doesn't make the model creative. it flattens the probability distribution over next tokens. high temp = more uniform distribution = more surprising word choices. that's it. creativity is an emergent illusion."

Rules:
  - Technically accurate — never sacrifice precision for punchiness
  - One idea per post, fully explained — not a listicle, not a teaser
  - No "we", "our team", "our company", "as a founder" — this is one engineer learning
  - No "your RAG is broken" style — this is not consulting advice, it's a learning share
  - Contractions are fine. Short sentences are fine. Lowercase is fine.
  - Never use: game-changer, revolutionary, groundbreaking, leverage, paradigm, delve, realm
  - If it reads like a LinkedIn post or a GPT summary, rewrite it
""".strip()

VIRAL_POST_PROMPT = """
Write one X post from the perspective of an AI/ML engineer actively learning — sharing something they just figured out, not presenting from authority.

Topic: {topic}
Tone: {tone}

Recent AI research and news to draw from (use specific numbers, mechanisms, findings — don't cite the source):
{research}

━━━ THE CORE TASK ━━━
Share one technically accurate insight that sounds like an engineer mid-discovery, not a textbook.

Wrong (expert presenting facts — avoid this):
  "transformers leverage attention mechanisms to understand contextual relationships"
  "RAG significantly improves LLM accuracy by grounding responses in retrieved data"

Right (engineer who just figured something out):
  "spent time on why LLMs fail at math. they don't see numbers — they see tokens. '1234' can split into '12' and '34'. it was never doing arithmetic. it was pattern-matching over fragments."
  "TIL the KV cache is why token 1 takes 200ms and token 500 takes 20ms. each new token only computes its own attention — prior key/values are cached. O(n²) → O(n). that's it."

Use the research to ground the insight in something concrete — a specific number, a paper finding, a real failure mode.

━━━ LEARNING-IN-PUBLIC VOICE ━━━
Sound like someone figuring this out, not someone who has it all figured out:
  "I got this wrong for a long time." / "here's what finally made it click." / "TIL that..."
  NOT: "here's the definitive breakdown" / "you need to understand" / "this is how experts do it"

{style_section}

━━━ HARD RULES ━━━
- Max 220 characters (hashtags + URL get added after — don't include them)
- No emojis
- No "we", "our", "our team", "our company"
- No hype words: game-changing, revolutionary, groundbreaking, paradigm, leverage, delve
- Plain text only, no markdown

OUTPUT: only the post body. no quotes, no labels, no hashtags.
""".strip()


THREAD_POST_PROMPT = """
Write a 6-tweet thread from the perspective of an AI/ML engineer actively learning — going deep on one concept, sharing what they discovered, not lecturing from authority.

Topic: {topic}
Tone: {tone}

Recent AI research and news to draw from (use specific numbers and findings, don't cite sources):
{research}

{style_section}

━━━ LEARNING-IN-PUBLIC VOICE ━━━
Right (engineer who's still figuring it out):
  "went deep on attention today. here's what every tutorial skips:"
  "I got this wrong for a long time — here's what finally made the KV cache click:"
  "TIL: each new token only computes its own attention. prior key/values are cached. that's O(n²) → O(n). that's why token 1 is slow and token 100 is fast."

Wrong (senior architect presenting from authority):
  "our team has implemented this at scale and here is what we learned"
  "as an experienced engineer, I can tell you definitively that..."
  "this revolutionary approach changes everything"
  "your system is broken because..."

━━━ RULES ━━━
- No "we", "our", "our team", "our company" anywhere in the thread
- Technically accurate in every tweet — never trade precision for punchiness
- Tweet 1 max 150 chars, tweets 2-6 max 280 chars each
- No hashtags, no emojis, plain text only

OUTPUT FORMAT: exactly 6 tweets separated by a line containing only "---". Nothing else.
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI RETRY + FALLBACK CHAIN  (key1 → key2 → Groq → Euron)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_retry_seconds(error: Exception) -> int:
    import re
    match = re.search(r"retryDelay['\"]:\s*['\"](\d+)s", str(error))
    return min(int(match.group(1)), 60) if match else RETRY_BASE_SECONDS


def _is_quota_error(error: Exception) -> bool:
    return "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error) or "quota" in str(error).lower()


def _is_retryable_server_error(error: Exception) -> bool:
    msg = str(error).lower()
    return "503" in msg or "unavailable" in msg or "high demand" in msg


def _is_daily_quota_exhausted(error: Exception) -> bool:
    s = str(error)
    return "PerDay" in s or "GenerateRequestsPerDay" in s or ("limit: 0" in s and "429" in s)


def _call_groq(prompt: str, system_instruction: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set.")
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(1, 4):
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages},
            timeout=90,
        )
        if resp.status_code == 429:
            wait = 20 * attempt
            print(f"  [Groq] 429 rate limit, attempt {attempt}/3. Waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    raise RuntimeError("Groq API failed after 3 attempts.")


def _call_euron(prompt: str, system_instruction: str) -> str:
    if not EURON_API_KEY:
        raise RuntimeError("EURON_API_KEY not set.")
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(1, 4):
        resp = requests.post(
            "https://api.euron.one/api/v1/euri/chat/completions",
            headers={"Authorization": f"Bearer {EURON_API_KEY}", "Content-Type": "application/json"},
            json={"model": "gemini-2.0-flash", "messages": messages},
            timeout=90,
        )
        if resp.status_code == 429:
            wait = 20 * attempt
            print(f"  [Euron] 429 rate limit, attempt {attempt}/3. Waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    raise RuntimeError("Euron API failed after 3 attempts.")


def generate_text(prompt: str, system_instruction: str) -> str:
    """Call Gemini with key rotation (key1 → key2 → Euron fallback)."""
    api_keys = [k for k in [GEMINI_API_KEY, GEMINI_API_KEY_2] if k]
    models_to_try = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    last_error = None

    for key_index, api_key in enumerate(api_keys):
        client = genai.Client(api_key=api_key)
        key_label = f"key#{key_index + 1} (...{api_key[-6:]})"
        daily_exhausted = False
        print(f"  [Gemini] Trying {key_label}")

        for model_id in models_to_try:
            if daily_exhausted:
                break
            config = types.GenerateContentConfig(system_instruction=system_instruction)
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = client.models.generate_content(
                        model=model_id, contents=prompt, config=config
                    )
                    print(f"  [Gemini] Success with {model_id} on {key_label}")
                    return response.text.strip()
                except Exception as e:
                    if _is_quota_error(e) or _is_retryable_server_error(e):
                        last_error = e
                        if _is_daily_quota_exhausted(e):
                            next_key = f"key#{key_index + 2}" if key_index + 1 < len(api_keys) else "Euron fallback"
                            print(f"  [Gemini] Daily quota exhausted on {key_label}. Switching to {next_key}.")
                            daily_exhausted = True
                            break
                        wait = _parse_retry_seconds(e)
                        kind = "quota (429)" if _is_quota_error(e) else "overloaded (503)"
                        print(f"  [Gemini] {kind} on {model_id} ({key_label}), attempt {attempt}/{MAX_RETRIES}. Retrying in {wait}s...")
                        if attempt < MAX_RETRIES:
                            time.sleep(wait)
                        else:
                            print(f"  [Gemini] Retries exhausted for {model_id}, trying next model.")
                            break
                    else:
                        raise

    # All Gemini keys exhausted → try Groq, then Euron
    if GROQ_API_KEY:
        try:
            print("  [Groq] All Gemini keys exhausted. Falling back to Groq...")
            return _call_groq(prompt, system_instruction)
        except Exception as e:
            print(f"  [Groq] Failed: {e}. Trying Euron...")
            last_error = e

    if EURON_API_KEY:
        print("  [Euron] Falling back to Euron...")
        return _call_euron(prompt, system_instruction)

    raise last_error or RuntimeError(
        "All Gemini keys exhausted and no Groq/Euron key configured. Try again tomorrow."
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Research with Exa
# ══════════════════════════════════════════════════════════════════════════════

def research_topic(topic: str, niche: str) -> str:
    """Find 5 recent high-quality articles on the topic and return a research brief."""
    print("\n[ Step 1 ] Researching topic with Exa...")

    exa = Exa(api_key=EXA_API_KEY)
    results = exa.search(
        query=f"{topic} {niche} 2026 news research announcement release",
        type="auto",
        num_results=5,
        start_published_date="2026-01-01",
        contents={
            "text": {"max_characters": 800},
            "highlights": {"num_sentences": 3},
        },
    )

    lines = []
    for i, result in enumerate(results.results, 1):
        title      = result.title or "Untitled"
        url        = result.url
        text       = (result.text or "")[:600].strip()
        highlights = result.highlights or []

        lines.append(f"Source {i}: {title}")
        lines.append(f"URL: {url}")
        if highlights:
            lines.append(f"Key insight: {highlights[0]}")
        if text:
            lines.append(f"Context: {text[:300]}...")
        lines.append("")

    brief = "\n".join(lines)
    print(f"  Found {len(results.results)} sources.\n")
    return brief


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Generate Viral Post with Gemini
# ══════════════════════════════════════════════════════════════════════════════

def generate_post(topic: str, tone: str, research: str, style_index: int = 0) -> str:
    """Call Gemini with the viral post prompt + research brief."""
    print(f"[ Step 2 ] Generating post with Gemini... (style: {_STYLE_LABELS[style_index]})")

    prompt = VIRAL_POST_PROMPT.format(
        topic=topic,
        tone=tone,
        research=research[:2000],
        style_section=_STYLE_SINGLE_SECTION[style_index],
    )

    post = generate_text(prompt, SYSTEM_PROMPT)

    # Strip surrounding quotes Gemini might add
    if post.startswith('"') and post.endswith('"'):
        post = post[1:-1].strip()
    if post.startswith("'") and post.endswith("'"):
        post = post[1:-1].strip()

    # Strip markdown formatting (X doesn't render it — shows as literal asterisks)
    import re as _re
    post = _re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', post)
    post = _re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', post)
    post = post.strip()

    # If over body budget, ask the model to shorten it (max 2 attempts)
    for shorten_attempt in range(2):
        if len(post) <= _BODY_CHAR_LIMIT:
            break
        print(f"  Post is {len(post)} chars — asking model to shorten (attempt {shorten_attempt + 1}/2)...")
        shorten_prompt = (
            f"This X post body is {len(post)} characters, over the {_BODY_CHAR_LIMIT}-character budget.\n\n"
            f"Shorten it to strictly under {_BODY_CHAR_LIMIT - 5} characters while keeping the same structure, voice, and impact.\n"
            f"(The final post also gets hashtags + a URL appended — keep this body tight.)\n"
            f"Keep the hook, the story, the lesson. Cut filler words, not ideas.\n"
            f"Plain text only — no markdown, no hashtags.\n\n"
            f"Original post:\n{post}\n\n"
            f"Output ONLY the shortened post. Nothing else."
        )
        post = generate_text(shorten_prompt, SYSTEM_PROMPT)
        post = _re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', post)
        post = _re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', post)
        post = post.strip()

    # Append 2 relevant hashtags + clickable portfolio URL
    hashtags = _pick_hashtags(post, topic)
    post = post + f"\n\n{hashtags}"
    if PORTFOLIO_URL:
        post = post + f"\n\n{PORTFOLIO_URL}"

    # X counts any URL as 23 chars (t.co) regardless of raw length
    x_len = len(post)
    if PORTFOLIO_URL and PORTFOLIO_URL in post:
        x_len = x_len - len(PORTFOLIO_URL) + _URL_TCOLEN

    print(f"\n  Generated post:\n  {'─'*50}")
    for line in post.split("\n"):
        print(f"  {line}")
    print(f"  {'─'*50}")
    print(f"  Character count: {len(post)} raw / {x_len} X-chars (max 280)\n")

    if x_len > 280:
        raise ValueError(f"Post still too long ({x_len} X-chars) after shortening attempts.")

    return post


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2b — Generate Thread with Gemini
# ══════════════════════════════════════════════════════════════════════════════

def generate_thread(topic: str, tone: str, research: str, style_index: int = 0) -> list:
    """Generate a 6-tweet thread. Returns [] on failure (caller falls back to single post)."""
    print(f"[ Step 2 ] Generating thread with Gemini... (style: {_STYLE_LABELS[style_index]})")

    # Resolve {portfolio_url} inside the style section before inserting into the outer template
    style_sec = _STYLE_THREAD_SECTION[style_index].format(portfolio_url=PORTFOLIO_URL)
    prompt = THREAD_POST_PROMPT.format(
        topic=topic,
        tone=tone,
        research=research[:2000],
        style_section=style_sec,
    )

    raw = generate_text(prompt, SYSTEM_PROMPT)

    import re as _re
    tweets = [t.strip() for t in raw.split("---") if t.strip()]
    tweets = [_re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', t) for t in tweets]
    tweets = [_re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', t).strip() for t in tweets]

    if len(tweets) < 3:
        print(f"  [Thread] Got {len(tweets)} tweets, expected 6. Falling back to single post.")
        return []

    tweets = tweets[:6]
    for i, tweet in enumerate(tweets):
        if len(tweet) > 280:
            tweets[i] = tweet[:277] + "..."

    # Append portfolio URL to last tweet if the model didn't include it
    if tweets and PORTFOLIO_URL:
        url_suffix = f"\n\n{PORTFOLIO_URL}"
        if PORTFOLIO_URL not in tweets[-1] and len(tweets[-1]) + len(url_suffix) <= 280:
            tweets[-1] = tweets[-1] + url_suffix

    print(f"\n  Generated {len(tweets)}-tweet thread:")
    print(f"  {'─'*50}")
    for i, tweet in enumerate(tweets, 1):
        preview = tweet[:100] + ("..." if len(tweet) > 100 else "")
        print(f"  [{i}] {preview}")
    print(f"  {'─'*50}\n")

    return tweets


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Schedule to Buffer
# ══════════════════════════════════════════════════════════════════════════════

class BufferRateLimitError(Exception):
    """Raised when Buffer API returns a rate limit error that cannot be retried within the run."""


def _is_buffer_rate_limit(data: dict) -> bool:
    """Return True if the Buffer GraphQL response indicates a rate limit error."""
    errors = data.get("errors")
    if not errors:
        return False
    raw = str(errors).lower()
    return "rate_limit_exceeded" in raw or "too many requests" in raw


def schedule_to_buffer(post_text: str, image_url: str = None) -> str:
    """Push the post to Buffer via GraphQL. Schedules 5 minutes from now.

    If image_url is given (a public URL), it is attached as a media image via
    Buffer's assets field. Buffer cannot upload files — the URL must be public.
    """
    print("[ Step 3 ] Scheduling to Buffer...")
    if image_url:
        print(f"  [Buffer] Attaching infographic: {image_url}")

    due_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    asset_decl  = ", $imageUrl: String!" if image_url else ""
    asset_field = "assets: [{ image: { url: $imageUrl } }]," if image_url else ""
    mutation = f"""
    mutation CreatePost($text: String!, $channelId: ChannelId!, $dueAt: DateTime{asset_decl}) {{
      createPost(input: {{
        text: $text,
        channelId: $channelId,
        schedulingType: automatic,
        mode: customScheduled,
        {asset_field}
        dueAt: $dueAt
      }}) {{
        ... on PostActionSuccess {{
          post {{
            id
            text
          }}
        }}
        ... on MutationError {{
          message
        }}
      }}
    }}
    """

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.post(
            "https://api.buffer.com/graphql",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {BUFFER_API_KEY}",
            },
            json={
                "query": mutation,
                "variables": {
                    "text": post_text,
                    "channelId": BUFFER_CHANNEL_ID,
                    "dueAt": due_at,
                    **({"imageUrl": image_url} if image_url else {}),
                },
            },
            timeout=30,
        )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else RETRY_BASE_SECONDS * attempt
            print(f"  Buffer HTTP 429 rate limit. Waiting {wait_seconds}s before retry {attempt}/{MAX_RETRIES}...")
            if attempt == MAX_RETRIES:
                raise BufferRateLimitError("Buffer rate limit (HTTP 429). The 15-minute window has not cleared.")
            time.sleep(wait_seconds)
            continue

        try:
            data = response.json()
        except ValueError:
            raise RuntimeError(f"Buffer API error: invalid JSON response (status {response.status_code})")

        if _is_buffer_rate_limit(data):
            errors = data.get("errors", [])
            # Extract the window duration from extensions if available
            window = "15m"
            if isinstance(errors, list) and errors:
                ext = errors[0].get("extensions", {})
                window = ext.get("window", window)
            print(f"  Buffer GraphQL rate limit (window: {window}), attempt {attempt}/{MAX_RETRIES}.")
            if attempt < MAX_RETRIES:
                wait_seconds = RETRY_BASE_SECONDS * attempt
                print(f"  Waiting {wait_seconds}s before retry...")
                time.sleep(wait_seconds)
                continue
            raise BufferRateLimitError(
                f"Buffer rate limit exceeded (window: {window}). "
                "Too many requests were made in a short period — likely from multiple workflow triggers. "
                "The post will be skipped today and retried tomorrow."
            )

        if "errors" in data:
            errors = data["errors"]
            message = errors[0].get("message") if isinstance(errors, list) and errors else str(errors)
            raise RuntimeError(f"Buffer API error: {message}")

        result = data.get("data", {}).get("createPost", {})
        if "message" in result:
            raise RuntimeError(f"Buffer mutation error: {result['message']}")

        post_id = result.get("post", {}).get("id", "unknown")
        print(f"  Scheduled! Buffer Post ID: {post_id}")
        print(f"  Publish time : {due_at}\n")
        return post_id

    raise RuntimeError("Buffer API error: exhausted retry attempts.")


def schedule_thread_to_buffer(tweets: list) -> str:
    """Push a thread to Buffer via GraphQL items input. Falls back to hook-only on API error."""
    print("[ Step 3 ] Scheduling thread to Buffer...")

    due_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    items = [{"text": t} for t in tweets]

    mutation = """
    mutation CreatePost($items: [PostItemInput!]!, $channelId: ChannelId!, $dueAt: DateTime) {
      createPost(input: {
        items: $items,
        channelId: $channelId,
        schedulingType: automatic,
        mode: customScheduled,
        dueAt: $dueAt
      }) {
        ... on PostActionSuccess {
          post { id text }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BUFFER_API_KEY}",
        },
        json={
            "query": mutation,
            "variables": {"items": items, "channelId": BUFFER_CHANNEL_ID, "dueAt": due_at},
        },
        timeout=15,
    )

    try:
        data = response.json()
    except ValueError:
        print("  [Thread] Buffer returned invalid JSON — falling back to hook tweet only...")
        return schedule_to_buffer(tweets[0])

    if response.status_code != 200 or "errors" in data:
        print("  [Thread] Buffer thread API error — falling back to hook tweet only...")
        return schedule_to_buffer(tweets[0])

    result = data.get("data", {}).get("createPost", {})
    if "message" in result:
        print(f"  [Thread] Buffer mutation error: {result['message']} — falling back to hook tweet only...")
        return schedule_to_buffer(tweets[0])

    post_id = result.get("post", {}).get("id", "unknown")
    print(f"  Scheduled thread! Buffer Post ID: {post_id}")
    print(f"  Publish time: {due_at}\n")
    return post_id


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3.5 — Infographic image (single posts only)
# ══════════════════════════════════════════════════════════════════════════════

def build_infographic_image(research: str, topic: str, preview: bool, style_index: int = 0):
    """Render the infographic and (unless preview) host it for Buffer.

    Returns a public image URL (real run), a local PNG path (preview), or None
    on any failure — so a single rendering hiccup never kills the daily post.
    """
    try:
        print("\n[ Step 3.5 ] Building infographic image...")
        framing  = _STYLE_INFOGRAPHIC_FRAMING[style_index]
        content  = infographic.generate_infographic_content(research, topic, generate_text, framing)
        out_dir  = os.path.join(_script_dir, "..", "output")
        os.makedirs(out_dir, exist_ok=True)
        png_path = os.path.abspath(os.path.join(out_dir, "infographic.png"))
        infographic.render_infographic(content, png_path)
        if preview:
            return png_path
        return infographic.upload_to_imgbb(png_path)
    except Exception as e:
        print(f"  [Infographic] Skipped — {e}. Falling back to text-only post.")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main(preview: bool = False):
    # Series day routing: Mon=RAG, Wed=Cloud, Fri=Agentic; other days pick freely
    weekday     = datetime.now(timezone.utc).weekday()
    series_name = _SERIES_DAY_MAP.get(weekday)
    if series_name and SERIES_TOPICS.get(series_name):
        topic = random.choice(SERIES_TOPICS[series_name])
    else:
        topic = random.choice(TOPICS)

    tone        = random.choice(TONES)
    style_index = _pick_style_index()
    is_thread   = random.random() < 0.30  # 30% chance of thread

    post_type = "THREAD (6 tweets)" if is_thread else "SINGLE POST"

    print(f"\n{'='*60}")
    print(f"  X Post Agent — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    if preview:
        print(f"  MODE: PREVIEW (no Buffer scheduling)")
    print(f"  Type   : {post_type}")
    print(f"{'='*60}")
    print(f"  Niche  : {NICHE}")
    if series_name:
        print(f"  Series : {series_name}")
    print(f"  Topic  : {topic}")
    print(f"  Tone   : {tone}")
    print(f"  Style  : Style {style_index + 1} — {_STYLE_LABELS[style_index]}")
    print(f"{'='*60}\n")

    try:
        research = research_topic(topic, NICHE)

        if is_thread:
            tweets = generate_thread(topic, tone, research, style_index)
            if not tweets:
                # Thread generation failed — fall through to single post
                is_thread = False

        if not is_thread:
            post = generate_post(topic, tone, research, style_index)

        if preview:
            if is_thread:
                print(f"  PREVIEW — Thread ({len(tweets)} tweets):")
                for i, t in enumerate(tweets, 1):
                    print(f"  [{i}] {t}\n")
            else:
                image_ref = None
                if INCLUDE_INFOGRAPHIC:
                    image_ref = build_infographic_image(research, topic, preview=True, style_index=style_index)
                if image_ref:
                    print(f"  Infographic saved at: {image_ref}")
            print(f"{'='*60}")
            print(f"  PREVIEW ONLY — post NOT sent to Buffer.")
            print(f"  Run without --preview to schedule it.")
            print(f"{'='*60}\n")
            return

        image_ref = None
        if not is_thread and INCLUDE_INFOGRAPHIC:
            image_ref = build_infographic_image(research, topic, preview=False, style_index=style_index)

        if is_thread:
            post_id = schedule_thread_to_buffer(tweets)
        else:
            post_id = schedule_to_buffer(post, image_ref)

        label = "Thread" if is_thread else "Post"
        print(f"{'='*60}")
        print(f"  Done! {label} queued in Buffer → will publish to X")
        print(f"  Buffer ID : {post_id}")
        print(f"{'='*60}\n")

    except BufferRateLimitError as e:
        # Buffer rate limit during a daily run — skip gracefully rather than failing the workflow.
        # Retrying within the 15-minute window will not help, and the post is already missed for today.
        print(f"\n  WARNING: {e}")
        print(f"  Tip: avoid triggering the workflow manually and via schedule on the same day.")
        print(f"  Exiting with code 0 — workflow will NOT be marked as failed.\n")
        raise SystemExit(0)

    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    import sys
    main(preview="--preview" in sys.argv)
