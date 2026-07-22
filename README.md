# X Post Automation

An AI agent that researches real AI/tech topics, generates educational posts about how AI technology actually works, and publishes them to X (Twitter) automatically — 3 times per day.

**No VPS needed. No manual work. Fully automated via GitHub Actions.**

---

## What It Posts

Pure AI technology education — the real mechanisms behind LLMs, transformers, RAG, agents, and the full AI stack. No business content, no hype, no product reviews.

Examples of the content direction:
- *"the KV cache is why your first token takes 200ms and the rest take 20ms. prior key-value pairs get cached so the model doesn't recompute context from scratch each step."*
- *"fine-tuning doesn't teach new facts. it shifts the output distribution toward a style. want new facts? use RAG. confusing these is a very expensive mistake."*
- *"your RAG returning wrong answers? 90% of the time it's not the embeddings. it's that your chunks are too large and the relevant sentence is buried in 500 tokens of noise."*

---

## How It Works

```
GitHub Actions (9 AM / 1 PM / 7 PM IST)
        ↓
Series routing — Mon: How It Actually Works
                 Wed: AI Stack Explained
                 Fri: AI Research Decoded
                 Other days: random topic
        ↓
Exa — neural web research on the selected topic
        ↓
Gemini — generates post
  └─ fallback: Gemini key #2 → Groq → Euron API
        ↓
[Single post] Playwright renders infographic PNG → imgbb hosts it
        ↓
Buffer — schedules and publishes to X (with infographic attached)
```

**Post type per run:**
- **Single post** with branded infographic image attached (100% of runs)

---

## Posting Schedule

| Time (IST) | UTC | Cron |
|---|---|---|
| 9:00 AM | 3:30 UTC | `30 3 * * *` |
| 1:00 PM | 7:30 UTC | `30 7 * * *` |
| 7:00 PM | 1:30 UTC | `30 13 * * *` |

3 posts per day, 7 days a week.

---

## Content Series

On Mon / Wed / Fri, the agent picks from a named series instead of a random topic:

| Day | Series | Focus |
|---|---|---|
| Monday | **How It Actually Works** | One AI concept explained from first principles (attention, KV cache, tokenization, RLHF…) |
| Wednesday | **AI Stack Explained** | System design and architecture (RAG pipeline, inference stack, agent loop, vector search…) |
| Friday | **AI Research Decoded** | Recent papers and findings decoded in plain technical English |

---

## Hashtag System

Two relevant hashtags are automatically selected per post based on content and appended after the body. Examples:

| Content matches | Tags added |
|---|---|
| attention, transformer, self-attention | `#Transformers #MachineLearning` |
| RAG, retrieval, vector, embedding | `#RAG #LLM` |
| agent, tool call, function call | `#AgenticAI #LLM` |
| fine-tuning, RLHF, DPO, LoRA | `#LLMTraining #MachineLearning` |
| KV cache, quantization, inference | `#LLMOps #MachineLearning` |
| diffusion, image generation | `#GenerativeAI #MachineLearning` |
| default | `#AI #MachineLearning` |

---

## Tech Stack

| Tool | Purpose |
|---|---|
| **GitHub Actions** | Scheduling (replaces VPS/cron) |
| **Exa** | Real-time neural web research |
| **Google Gemini** | Post generation (dual-key with quota rotation) |
| **Groq** | Fallback LLM (llama-3.3-70b) |
| **Euron API** | Last-resort fallback (gemini-2.0-flash) |
| **Playwright** | Renders infographic HTML template to PNG |
| **imgbb** | Hosts the PNG so Buffer can attach it |
| **Buffer** | Schedules and publishes to X |

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/vipinvishal/X-Post-Automation.git
cd X-Post-Automation
```

### 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

### 3. Set up your `.env` file

```bash
cp .env.example .env
```

Fill in your API keys (see [Configuration](#configuration) below).

### 4. Test locally

```bash
# Preview — generates post + infographic, does NOT send to Buffer
python scripts/generate_and_schedule.py --preview

# Full run — research → generate → infographic → schedule to Buffer
python scripts/generate_and_schedule.py
```

---

## Configuration

### Required secrets (`.env` / GitHub Actions secrets)

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `EXA_API_KEY` | [exa.ai](https://exa.ai) |
| `BUFFER_API_KEY` | buffer.com → Settings → API |
| `BUFFER_CHANNEL_ID` | Run `python scripts/get_buffer_channel.py` |
| `IMGBB_API_KEY` | [api.imgbb.com](https://api.imgbb.com) — free tier is enough |

### Optional secrets

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY_2` | Second Gemini key for quota fallback |
| `GROQ_API_KEY` | Groq fallback (llama-3.3-70b) |
| `EURON_API_KEY` | Euron last-resort fallback |

> **Note:** If `IMGBB_API_KEY` is not set, the infographic step is skipped and the post publishes as text-only. The run never fails because of a missing image key.

### Optional env vars

| Variable | Default | Purpose |
|---|---|---|
| `INCLUDE_INFOGRAPHIC` | `1` | Set to `0` to disable infographic generation entirely |
| `INFOGRAPHIC_HANDLE` | `@VipinAILabs` | Handle shown on infographic |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Primary Gemini model |

### Finding your Buffer Channel ID

```bash
# Make sure BUFFER_API_KEY is in .env first
python scripts/get_buffer_channel.py
```

Copy the ID for your X channel and set it as `BUFFER_CHANNEL_ID`.

---

## GitHub Actions Setup

### 1. Add secrets

Go to **Settings → Secrets and variables → Actions** and add:

**Secrets:** `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GROQ_API_KEY`, `EURON_API_KEY`, `EXA_API_KEY`, `BUFFER_API_KEY`, `BUFFER_CHANNEL_ID`, `IMGBB_API_KEY`

**Variables:** `INFOGRAPHIC_HANDLE` (e.g. `@VipinAILabs`)

### 2. The workflow runs automatically

Defined in `.github/workflows/daily_post.yml`. Triggers at 9 AM, 1 PM, and 7 PM IST every day.

Manual trigger: **Actions → Daily X Post → Run workflow**

---

## Customizing Content

Edit `scripts/topics.json` to change:

| Key | What it controls |
|---|---|
| `niche` | The content category fed to Exa for research |
| `persona` | The voice and style context passed to Gemini |
| `topics` | General topic pool (used on non-series days) |
| `series_topics` | Topics for each named series (Mon/Wed/Fri) |
| `tones` | Tones randomly applied to each post |
| `formats` | Format styles for single posts |

To change the series schedule, edit `_SERIES_DAY_MAP` in `scripts/generate_and_schedule.py`.

---

## Project Structure

```
├── scripts/
│   ├── generate_and_schedule.py   # main pipeline
│   ├── topics.json                # niche, topics, series, tones, formats
│   ├── infographic.py             # infographic content gen + imgbb upload
│   └── get_buffer_channel.py      # one-time helper to find Buffer channel ID
├── renderer/
│   ├── render.py                  # Playwright HTML → PNG renderer
│   ├── templates/
│   │   └── infographic.html.j2    # Jinja2 infographic template
│   └── fonts/                     # embedded handwriting fonts
├── .github/
│   └── workflows/
│       └── daily_post.yml         # GitHub Actions workflow
├── .env.example                   # template — copy to .env and fill in keys
├── requirements.txt               # Python dependencies
└── .gitignore
```

---

## Fallback Chain

```
Gemini key #1
    → Gemini key #2 (if GEMINI_API_KEY_2 is set)
        → Groq / llama-3.3-70b (if GROQ_API_KEY is set)
            → Euron API / gemini-2.0-flash (if EURON_API_KEY is set)
```

No manual intervention needed on quota exhaustion.

---

## License

MIT
