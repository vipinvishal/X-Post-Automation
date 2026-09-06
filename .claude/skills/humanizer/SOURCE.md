Vendored from https://github.com/blader/humanizer (MIT license, see LICENSE).

`SKILL.md` is copied verbatim (version 2.11.2 at time of install) so future
updates should be pulled from upstream rather than hand-edited here.

Used in this project to check that generated X posts and infographic text
don't read like AI-generated prose (see the "Signs of AI writing" patterns
this skill is built on). The pipeline's prompts in `scripts/generate_and_schedule.py`
and `scripts/infographic.py` were hardened against the most relevant patterns
directly (no em/en dashes, no curly quotes, banned AI-tell words, no chatbot
leftovers). This skill is for manually humanizing any other draft text on
demand (`/humanizer` or "humanize this: ...").
