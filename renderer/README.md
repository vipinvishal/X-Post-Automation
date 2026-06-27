# VipinAIHub Daily Infographic System

Auto-generate branded, hand-drawn-style educational infographics for Instagram /
Threads / LinkedIn — one per day, from a topic queue.

This package is **Step 1 (the foundation): a placeholder template + auto-fit
renderer.** Change the content JSON → get a correctly-laid-out PNG, every time,
with no manual nudging.

## What's here

```
infographic-system/
├── templates/
│   └── infographic.html.j2     # the brand template (HTML/CSS + Jinja2 slots)
├── icons.py                    # reusable SVG icons, picked by name per stage
├── render.py                   # fills template → auto-fits text → PNG (Playwright)
├── fonts/
│   ├── *.ttf                   # handwritten fonts (Kalam, Caveat, Gochi Hand)
│   └── embedded_fonts.css      # fonts base64-embedded — NO network needed
├── data/
│   ├── portrait_b64.txt        # your portrait, embedded into every render
│   ├── sample_content.json     # the S3 example (the content schema)
│   └── test_https.json         # a 2nd topic proving variable text auto-fits
└── output/                     # rendered PNGs land here
```

## Fonts (why they're embedded)

Google Fonts is often blocked on servers/CI. So the fonts are downloaded once,
base64-embedded into `fonts/embedded_fonts.css`, and injected at render time —
they render identically everywhere with zero network dependency.

- **Caveat** — the flowing marker headline script (titles, number circles)
- **Kalam** — hand-lettered body text. Bonus: it's an Indian Type Foundry font
  with Devanagari support, so it renders **Hindi / Hinglish** correctly too.
- **Gochi Hand** — available as an alt if you want to rotate styles.

To refresh or add fonts: drop a .ttf in `fonts/`, then rebuild the CSS:
```python
import base64
b64 = base64.b64encode(open('fonts/NAME.ttf','rb').read()).decode()
# append an @font-face rule to fonts/embedded_fonts.css
```

## Why HTML/CSS instead of hand-placed SVG

The original infographic was hand-tuned — every text-overflow and gap was fixed
by eye. A daily bot can't eyeball. CSS does the work instead: flexbox + text
wrapping + a font auto-shrink pass (`render.py: autofit()`) guarantee that
titles of any length fit their boxes. `test_https.json` has deliberately long
titles ("Client Hello & Certificate") and they wrap cleanly with zero edits.

## Run it

```bash
pip install playwright jinja2 --break-system-packages
python -m playwright install chromium

cd infographic-system
python render.py data/sample_content.json output/infographic.png
python render.py data/test_https.json   output/test_https.png
```

Output is 2x scale (~1800px wide) — crisp for social.

## The content schema (what the LLM must produce)

Every field in `sample_content.json` is a slot. The generator's only job is to
fill these for a new topic, respecting limits:

| field                | guidance                                        |
|----------------------|-------------------------------------------------|
| headline_line1_*     | split so the highlighted word sits in `_hl`     |
| headline_line2       | the blue second line                            |
| sub_pre/num/post     | the yellow pill; num is the stage count         |
| stages[].title       | <= ~22 chars ideal (auto-fit catches overflow)  |
| stages[].subtitle    | <= ~30 chars, one line                          |
| stages[].icon        | one of icons.py keys (upload, key, lock, ...)   |
| stages[].arrow_note  | tiny label on the arrow ("" on the last stage)  |
| explainers[].tag     | short heading; .body may use <span class=k1/k2/k3> and <b> |
| sticky1 / sticky2    | short; <b> for the colored word                 |
| terminal_cmd         | the fake shell command in the doodle            |
| quote_main           | use <span class=n> for number, <span class=h> for highlight |
| quote_sub            | one supporting line                             |
| handle               | always @VipinAIHub                              |

Available icon names: upload, laptop, copies, database, lock, cloud, gear,
file, search, key, network.

---

## Remaining build steps (the rest of the plan)

**Step 2 — Content generator (Claude API).**
Script: prompt Claude with a topic + this schema, demand JSON only, validate it
(retry if a title is too long or a field is missing). Output → a content JSON.

**Step 3 — Topic queue.**
A `topics.json` (or Google Sheet / Airtable) of 30-40 ideas across your niches
(AWS, Git, system design, Linux, networking...). Daily job pops the next unused
one. Keeps you in editorial control; avoids the bot inventing something wrong.

**Step 4 — Caption generator.**
Second Claude call: turn the topic into a Hinglish caption + hashtags tuned per
platform (IG vs LinkedIn vs Threads tone). This is where your India angle lives.

**Step 5 — Schedule.**
GitHub Actions cron (free) or Render cron. Runs daily: pop topic → generate
content → render PNG → generate caption → drop both into an output folder or a
Buffer queue.

**Step 6 — Posting (start semi-manual).**
Phase 1: system drops image+caption into Buffer; you tap approve. Phase 2: once
you trust output, automate via Buffer/Make.com (IG Graph API and LinkedIn API
need app approval; Buffer skips that pain). Threads now has an official API too.

**Quality guardrails (important):**
- Rotate 2-3 visual templates + vary topics so the feed doesn't look bot-made;
  samey daily output *hurts* reach.
- Always keep a human approval gate at first. One wrong technical claim posted
  automatically can cost credibility.

## Next action
Step 2: build the Claude API content generator with strict JSON validation.
