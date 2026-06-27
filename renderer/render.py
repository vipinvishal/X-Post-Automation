#!/usr/bin/env python3
"""Render an infographic PNG from a content JSON file.

Usage:
    python render.py data/sample_content.json output/infographic.png

The auto-fit pass measures each stage title in the real browser and shrinks
the font until it fits its box, so variable-length LLM output never overflows.
"""
import sys, json, base64, pathlib
from jinja2 import Template
from playwright.sync_api import sync_playwright
from icons import get_icon

ROOT = pathlib.Path(__file__).parent
TEMPLATE = ROOT / "templates" / "infographic.html.j2"
PORTRAIT_B64 = (ROOT / "data" / "portrait_b64.txt").read_text().strip()
FONT_CSS = (ROOT / "fonts" / "embedded_fonts.css").read_text()


def build_html(content):
    tpl = Template(TEMPLATE.read_text())
    # inject icon SVGs into stages
    for st in content["stages"]:
        st["icon"] = get_icon(st.get("icon", "file"))
    content["portrait_b64"] = PORTRAIT_B64
    content["font_css"] = FONT_CSS
    return tpl.render(**content)


def autofit(page):
    """Shrink any .stage .t that overflows its container. Runs in-browser."""
    page.evaluate("""() => {
        document.querySelectorAll('.stage .txt .t').forEach(el => {
            let size = parseFloat(getComputedStyle(el).fontSize);
            const box = el.parentElement;            // .txt
            while ((el.scrollWidth > box.clientWidth || el.scrollHeight > 60) && size > 13) {
                size -= 1;
                el.style.fontSize = size + 'px';
            }
        });
        // shrink headline if it overflows its column
        const h = document.querySelector('.headline h1');
        const col = document.querySelector('.headline');
        let hs = parseFloat(getComputedStyle(h).fontSize);
        while (h.scrollWidth > col.clientWidth && hs > 30) {
            hs -= 1; h.style.fontSize = hs + 'px';
        }
        // shrink sticky-note / terminal text until it fits its box
        // (no horizontal overflow and a sane max height so notes never clip)
        document.querySelectorAll('.sticky').forEach(el => {
            const maxH = el.classList.contains('term') ? 78 : 96;
            let size = parseFloat(getComputedStyle(el).fontSize);
            const inner = el.querySelector('.cmd') || el;   // shrink the cmd line if present
            let isz = parseFloat(getComputedStyle(inner).fontSize);
            while ((el.scrollWidth > el.clientWidth || el.scrollHeight > maxH)
                   && size > 9) {
                size -= 1; isz -= 1;
                el.style.fontSize = size + 'px';
                if (inner !== el) inner.style.fontSize = Math.max(isz, 8) + 'px';
            }
        });
    }""")


def render(content_path, out_path):
    content = json.loads(pathlib.Path(content_path).read_text())
    html = build_html(content)
    tmp_html = ROOT / "output" / "_tmp.html"
    tmp_html.parent.mkdir(parents=True, exist_ok=True)   # gitignored dir; create on fresh checkouts (CI)
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_html.write_text(html)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 1120},
                                device_scale_factor=2)   # 2x = crisp 1800px PNG
        page.goto(tmp_html.as_uri())
        page.wait_for_timeout(400)        # let fonts load
        autofit(page)
        page.wait_for_timeout(100)
        el = page.query_selector(".page")
        el.screenshot(path=str(out_path))
        browser.close()
    print(f"rendered -> {out_path}")


if __name__ == "__main__":
    cpath = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "sample_content.json")
    opath = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "output" / "infographic.png")
    render(cpath, opath)
