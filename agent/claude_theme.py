"""Claude.ai-inspired theme — global CSS injection for the Streamlit pages.

Call inject_global_styles() once near the top of each page (after
st.set_page_config). The page's existing content is left untouched —
this module only restyles widgets via CSS.

Palette
-------
cream      #FAF9F5   page background (Claude's signature warm off-white)
parchment  #F0EEE6   secondary surfaces, hover ground
linen      #E8E6DC   subtle borders
ink        #1F1E1D   primary text
graphite   #5B5A57   secondary text
mist       #8C8B86   muted captions, metadata
coral      #CC785C   accent (Claude's copper) — used sparingly
deep       #30302E   sidebar background

Fonts (all free, pulled via CSS @import)
-----
display   Source Serif 4
body      Inter
mono      JetBrains Mono

Injection method
----------------
st.html() rather than st.markdown(unsafe_allow_html=True). Streamlit's
markdown sanitizer otherwise mangles <style> blocks that contain unusual
content. The CSS deliberately contains no literal HTML tags (no <svg>
data URLs, no tags inside comments) for the same reason.
"""
from __future__ import annotations

import streamlit as st


_PALETTE = {
    "cream":     "#FAF9F5",
    "parchment": "#F0EEE6",
    "linen":     "#E8E6DC",
    "ink":       "#1F1E1D",
    "graphite":  "#5B5A57",
    "mist":      "#8C8B86",
    "coral":     "#CC785C",
    "coral_dim": "#B8674C",
    "coral_soft":"rgba(204, 120, 92, 0.10)",
    "deep":      "#30302E",
}


_GOOGLE_FONTS_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600"
    "&family=Inter:wght@300;400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500"
    "&display=swap');"
)


def inject_global_styles() -> None:
    """Emit a single <style> block defining the Claude-style theme."""
    payload = "<style>" + _GOOGLE_FONTS_IMPORT + _build_css() + "</style>"
    if hasattr(st, "html"):
        st.html(payload)
    else:
        st.markdown(payload, unsafe_allow_html=True)


def _build_css() -> str:
    p = _PALETTE
    return f"""
/* Claude-style core tokens */
:root {{
    --cream:      {p['cream']};
    --parchment:  {p['parchment']};
    --linen:      {p['linen']};
    --ink:        {p['ink']};
    --graphite:   {p['graphite']};
    --mist:       {p['mist']};
    --coral:      {p['coral']};
    --coral-dim:  {p['coral_dim']};
    --coral-soft: {p['coral_soft']};
    --deep:       {p['deep']};
    --display:    'Source Serif 4', 'Iowan Old Style', Georgia, serif;
    --body:       'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --mono:       'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
    --radius-sm:  6px;
    --radius:     10px;
    --radius-lg:  14px;
    --shadow-soft: 0 1px 2px rgba(31, 30, 29, 0.04);
}}

/* Page surface */
html, body, [data-testid="stAppViewContainer"], .stApp {{
    background: var(--cream) !important;
    color: var(--ink);
    font-family: var(--body);
    font-feature-settings: "ss01", "cv11";
    -webkit-font-smoothing: antialiased;
}}

/* Hide ONLY the auto-generated multipage nav — keep the top toolbar
   (hamburger / theme toggle) visible. */
[data-testid="stSidebarNav"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}

/* Typography */
h1, h2, h3, h4 {{
    font-family: var(--display) !important;
    color: var(--ink);
    font-weight: 500;
    letter-spacing: -0.012em;
    line-height: 1.18;
}}
h1 {{ font-size: clamp(1.9rem, 3.6vw, 2.6rem); }}
h2 {{ font-size: clamp(1.35rem, 2.4vw, 1.75rem); }}
h3 {{ font-size: 1.2rem; }}
h4 {{ font-size: 1rem; color: var(--graphite); }}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{
    font-family: var(--body);
    color: var(--ink);
    font-size: 0.96rem;
    line-height: 1.65;
}}
[data-testid="stCaptionContainer"],
small {{
    font-family: var(--body) !important;
    font-size: 0.84rem !important;
    color: var(--mist) !important;
}}
code, kbd, pre, [data-testid="stCode"] {{
    font-family: var(--mono) !important;
    font-size: 0.86em;
}}

/* Buttons — quiet pill style, coral primary */
.stButton > button, .stDownloadButton > button {{
    background: var(--cream);
    color: var(--ink);
    border: 1px solid var(--linen);
    border-radius: var(--radius);
    font-family: var(--body);
    font-weight: 500;
    font-size: 0.92rem;
    letter-spacing: -0.005em;
    padding: 0.55rem 1.1rem;
    transition: background 0.16s ease, color 0.16s ease, border-color 0.16s ease;
    box-shadow: none !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background: var(--parchment);
    color: var(--ink);
    border-color: var(--mist);
}}
.stButton > button:active, .stDownloadButton > button:active {{
    background: var(--linen);
}}
.stButton > button:focus:not(:active),
.stDownloadButton > button:focus:not(:active) {{
    outline: none;
    border-color: var(--coral);
}}

/* Primary — coral fill */
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
    background: var(--coral);
    color: var(--cream);
    border-color: var(--coral);
}}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {{
    background: var(--coral-dim);
    color: var(--cream);
    border-color: var(--coral-dim);
}}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
    background: var(--cream) !important;
    border: 1px solid var(--linen) !important;
    border-radius: var(--radius) !important;
    box-shadow: none !important;
    color: var(--ink) !important;
    font-family: var(--body) !important;
    font-size: 0.95rem !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
    border-color: var(--coral) !important;
    outline: none !important;
}}
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div {{
    border: none !important;
    background: transparent !important;
}}

/* Chat input */
[data-testid="stChatInput"] {{
    background: var(--cream);
    border-top: 1px solid var(--linen);
}}
[data-testid="stChatInput"] textarea {{
    background: var(--parchment) !important;
    border-radius: var(--radius-lg) !important;
    border: 1px solid var(--linen) !important;
    font-family: var(--body) !important;
    font-size: 0.96rem !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: var(--deep) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}}
[data-testid="stSidebar"] * {{
    color: var(--cream) !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: var(--cream) !important;
    font-family: var(--display) !important;
    font-weight: 500;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    color: rgba(250, 249, 245, 0.50) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255, 255, 255, 0.08) !important;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255, 255, 255, 0.04);
    color: var(--cream);
    border-color: rgba(255, 255, 255, 0.12);
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.22);
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: var(--coral);
    color: var(--cream);
    border-color: var(--coral);
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
    background: var(--coral-dim);
    border-color: var(--coral-dim);
}}
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stTextArea textarea {{
    background: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(255, 255, 255, 0.15) !important;
    color: var(--cream) !important;
}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px dashed rgba(255, 255, 255, 0.18) !important;
    border-radius: var(--radius) !important;
    color: var(--cream) !important;
}}
[data-testid="stSidebar"] [data-testid="stAlert"] {{
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    border-radius: var(--radius) !important;
    box-shadow: none !important;
}}

/* Bordered containers — gentle Claude-style card, no shadow */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid var(--linen) !important;
    border-radius: var(--radius-lg) !important;
    background: var(--cream);
    box-shadow: var(--shadow-soft);
    transition: border-color 0.18s ease, background 0.18s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color: var(--mist);
}}
/* Keep the dashboard card flex column so the Start button stays at the bottom */
[data-testid="stVerticalBlockBorderWrapper"] > div:first-child > [data-testid="stVerticalBlock"] {{
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 1.5rem 1.4rem 1.3rem;
    gap: 0.4rem;
}}
[data-testid="stVerticalBlockBorderWrapper"] > div:first-child > [data-testid="stVerticalBlock"] > div:last-child {{
    margin-top: auto;
}}

/* Expanders */
[data-testid="stExpander"] {{
    border: 1px solid var(--linen) !important;
    border-radius: var(--radius) !important;
    background: var(--cream);
    box-shadow: none !important;
    margin-bottom: 0.55rem;
}}
[data-testid="stExpander"] summary {{
    font-family: var(--body) !important;
    font-weight: 500;
    font-size: 0.95rem;
    padding: 0.65rem 0.95rem;
    color: var(--ink);
}}
[data-testid="stExpander"] summary:hover {{
    background: var(--parchment);
}}

/* Alerts */
[data-testid="stAlert"] {{
    border-radius: var(--radius) !important;
    border: 1px solid var(--linen) !important;
    background: var(--parchment) !important;
    box-shadow: none !important;
}}
[data-baseweb="notification"] {{
    border-radius: var(--radius) !important;
}}

/* Chat messages */
[data-testid="stChatMessage"] {{
    background: var(--cream) !important;
    border: 1px solid var(--linen);
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-soft);
    margin-bottom: 0.9rem;
}}

/* Divider */
hr {{
    border: 0;
    border-top: 1px solid var(--linen);
    margin: 1.5rem 0;
}}

/* Dialog */
[data-testid="stDialog"] > div, [role="dialog"] {{
    border: 1px solid var(--linen) !important;
    border-radius: var(--radius-lg) !important;
    background: var(--cream) !important;
    box-shadow: 0 12px 40px rgba(31, 30, 29, 0.10) !important;
}}

/* Spinner accent */
[data-testid="stSpinner"] > div > div {{
    border-top-color: var(--coral) !important;
}}

/* File uploader (main panel) */
[data-testid="stFileUploaderDropzone"] {{
    background: var(--parchment) !important;
    border: 1px dashed var(--mist) !important;
    border-radius: var(--radius) !important;
}}
"""
