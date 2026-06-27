"""SVG icon snippets keyed by name. The content generator picks an icon name
per stage; the renderer swaps in the SVG. Keeping icons here (not in the LLM
output) guarantees they always render correctly."""

ICONS = {
    "upload": '''<svg width="40" height="40" viewBox="0 0 44 44"><rect x="6" y="8" width="32" height="22" rx="3" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><line x1="2" y1="34" x2="42" y2="34" stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round"/><path d="M22 26 V14 M16 19 L22 13 L28 19" fill="none" stroke="#1f8fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>''',
    "laptop": '''<svg width="40" height="40" viewBox="0 0 44 44"><rect x="6" y="8" width="32" height="22" rx="3" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><line x1="2" y1="34" x2="42" y2="34" stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round"/><rect x="11" y="12" width="22" height="13" fill="#1f8fff" opacity="0.3"/></svg>''',
    "copies": '''<svg width="40" height="40" viewBox="0 0 44 44"><rect x="8" y="10" width="20" height="26" rx="3" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><rect x="18" y="6" width="20" height="26" rx="3" fill="#c7f0c2" stroke="#1a1a1a" stroke-width="2.5"/></svg>''',
    "database": '''<svg width="40" height="40" viewBox="0 0 44 44"><ellipse cx="22" cy="11" rx="15" ry="5" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><path d="M7 11 V33 a15 5 0 0 0 30 0 V11" fill="#ffd6ea" stroke="#1a1a1a" stroke-width="2.5"/><ellipse cx="22" cy="22" rx="15" ry="5" fill="none" stroke="#1a1a1a" stroke-width="1.8"/></svg>''',
    "lock": '''<svg width="40" height="40" viewBox="0 0 44 44"><rect x="9" y="19" width="26" height="20" rx="3" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><path d="M14 19 V13 a8 8 0 0 1 16 0 V19" fill="none" stroke="#1a1a1a" stroke-width="2.5"/><circle cx="22" cy="28" r="3" fill="#1a1a1a"/></svg>''',
    "cloud": '''<svg width="40" height="40" viewBox="0 0 44 44"><path d="M12 30 a8 8 0 0 1 1 -16 a10 10 0 0 1 19 3 a7 7 0 0 1 -2 13 Z" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/></svg>''',
    "gear": '''<svg width="40" height="40" viewBox="0 0 44 44"><circle cx="22" cy="22" r="8" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><g stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round"><line x1="22" y1="6" x2="22" y2="12"/><line x1="22" y1="32" x2="22" y2="38"/><line x1="6" y1="22" x2="12" y2="22"/><line x1="32" y1="22" x2="38" y2="22"/></g></svg>''',
    "file": '''<svg width="40" height="40" viewBox="0 0 44 44"><path d="M12 6 H28 L36 14 V38 H12 Z" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><path d="M28 6 V14 H36" fill="none" stroke="#1a1a1a" stroke-width="2.5"/></svg>''',
    "search": '''<svg width="40" height="40" viewBox="0 0 44 44"><circle cx="19" cy="19" r="11" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><line x1="27" y1="27" x2="37" y2="37" stroke="#1a1a1a" stroke-width="3" stroke-linecap="round"/></svg>''',
    "key": '''<svg width="40" height="40" viewBox="0 0 44 44"><circle cx="15" cy="15" r="9" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><path d="M21 21 L36 36 M30 30 L34 26 M33 33 L37 29" fill="none" stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round"/></svg>''',
    "network": '''<svg width="40" height="40" viewBox="0 0 44 44"><circle cx="22" cy="9" r="5" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><circle cx="9" cy="33" r="5" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><circle cx="35" cy="33" r="5" fill="#fff" stroke="#1a1a1a" stroke-width="2.5"/><path d="M22 14 L9 28 M22 14 L35 28" stroke="#1a1a1a" stroke-width="2.2"/></svg>''',
}

def get_icon(name):
    return ICONS.get(name, ICONS["file"])
