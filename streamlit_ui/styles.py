"""CSS constants and theme data matching the Next.js frontend."""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Category colours  (matches Next.js CATEGORY_COLORS in constants.ts)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CategoryColor:
    bg: str
    text: str
    border: str


CATEGORY_COLORS: dict[str, CategoryColor] = {
    "equity": CategoryColor("rgba(59,130,246,0.15)", "#60a5fa", "rgba(59,130,246,0.3)"),
    "debt": CategoryColor("rgba(245,158,11,0.15)", "#fbbf24", "rgba(245,158,11,0.3)"),
    "convertible_note": CategoryColor("rgba(139,92,246,0.15)", "#a78bfa", "rgba(139,92,246,0.3)"),
    "safe": CategoryColor("rgba(16,185,129,0.15)", "#34d399", "rgba(16,185,129,0.3)"),
    "fund_interest": CategoryColor("rgba(6,182,212,0.15)", "#22d3ee", "rgba(6,182,212,0.3)"),
    "real_estate": CategoryColor("rgba(249,115,22,0.15)", "#fb923c", "rgba(249,115,22,0.3)"),
    "revenue_share": CategoryColor("rgba(244,63,94,0.15)", "#fb7185", "rgba(244,63,94,0.3)"),
    "other": CategoryColor("rgba(100,116,139,0.15)", "#94a3b8", "rgba(100,116,139,0.3)"),
}

# ---------------------------------------------------------------------------
# Category codes  (matches Next.js CATEGORY_CODES in constants.ts)
# ---------------------------------------------------------------------------
CATEGORY_CODES: dict[str, tuple[str, str]] = {
    "equity": ("A01", "Equity Securities"),
    "debt": ("A02", "Debt Securities"),
    "convertible_note": ("A03", "Convertible Notes"),
    "safe": ("A04", "SAFE Instruments"),
    "real_estate": ("A05", "Real Estate Securities"),
    "revenue_share": ("A06", "Revenue Participation"),
    "fund_interest": ("A08", "Private Equity Funds"),
    "other": ("A99", "Unclassified"),
}

CATEGORY_LABELS: dict[str, str] = {
    "equity": "Equity",
    "debt": "Debt",
    "convertible_note": "Convertible Note",
    "safe": "SAFE",
    "fund_interest": "Fund Interest",
    "real_estate": "Real Estate",
    "revenue_share": "Revenue Share",
    "other": "Other",
}

CATEGORY_OPTIONS = list(CATEGORY_CODES.keys())

# ---------------------------------------------------------------------------
# Difficulty badge colours  (matches DIFFICULTY_COLORS)
# ---------------------------------------------------------------------------
DIFFICULTY_COLORS: dict[str, tuple[str, str]] = {
    "easy": ("rgba(16,185,129,0.15)", "#34d399"),
    "medium": ("rgba(245,158,11,0.15)", "#fbbf24"),
    "hard": ("rgba(244,63,94,0.15)", "#fb7185"),
}

# ---------------------------------------------------------------------------
# Source type colours for reasoning chain
# ---------------------------------------------------------------------------
SOURCE_COLORS: dict[str, tuple[str, str]] = {
    "Database": ("rgba(59,130,246,0.15)", "#60a5fa"),
    "Internal Database": ("rgba(59,130,246,0.15)", "#60a5fa"),
    "SEC Filing": ("rgba(245,158,11,0.15)", "#fbbf24"),
    "SEC EDGAR": ("rgba(245,158,11,0.15)", "#fbbf24"),
    "Web Search": ("rgba(139,92,246,0.15)", "#a78bfa"),
    "Public Web": ("rgba(139,92,246,0.15)", "#a78bfa"),
    "User Answer": ("rgba(16,185,129,0.15)", "#34d399"),
    "Human Input": ("rgba(16,185,129,0.15)", "#34d399"),
}

# ---------------------------------------------------------------------------
# Stage labels  (matches STAGE_LABELS in constants.ts)
# ---------------------------------------------------------------------------
STAGE_LABELS: dict[str, str] = {
    "I": "Stage I \u2014 Initial Assessment",
    "II": "Stage II \u2014 Research & Data Gathering",
    "III": "Stage III \u2014 Confidence Assessment",
    "IV": "Stage IV \u2014 Action Planning",
    "V": "Stage V \u2014 Classification",
    "VI": "Stage VI \u2014 Verification",
}

# ---------------------------------------------------------------------------
# Icons  (Unicode — Streamlit's markdown sanitiser strips SVG elements)
# ---------------------------------------------------------------------------
ICON_SHIELD = '<span style="font-size:1.1rem">&#x1F6E1;</span>'
ICON_CHECK = '<span style="color:#34d399;font-size:0.9rem">&#x2714;</span>'
ICON_CLOCK = '<span style="font-size:0.8rem">&#x23F1;</span>'
ICON_ALERT = '<span style="color:#fbbf24;font-size:1rem">&#x26A0;</span>'
ICON_DATABASE = '<span style="font-size:0.8rem">&#x1F5C4;</span>'
ICON_FILE_TEXT = '<span style="font-size:0.8rem">&#x1F4C4;</span>'
ICON_GLOBE = '<span style="font-size:0.8rem">&#x1F310;</span>'
ICON_USER = '<span style="font-size:0.8rem">&#x1F464;</span>'
ICON_SEARCH = '<span style="font-size:0.75rem">&#x1F50D;</span>'
ICON_TRENDING_UP = '<span style="font-size:0.8rem">&#x1F4C8;</span>'
ICON_SCALE = '<span style="font-size:0.85rem">&#x2696;</span>'
ICON_BOOK_OPEN = '<span style="font-size:0.75rem">&#x1F4D6;</span>'

SOURCE_ICONS: dict[str, str] = {
    "Internal Database": ICON_DATABASE,
    "Database": ICON_DATABASE,
    "SEC EDGAR": ICON_FILE_TEXT,
    "SEC Filing": ICON_FILE_TEXT,
    "Public Web": ICON_GLOBE,
    "Web Search": ICON_GLOBE,
    "Human Input": ICON_USER,
    "User Answer": ICON_USER,
}


# ---------------------------------------------------------------------------
# Main CSS stylesheet
# ---------------------------------------------------------------------------
def get_stylesheet() -> str:
    """Return the full CSS stylesheet for injection into the Streamlit app."""
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* ── Base typography ────────────────────────────────────────── */
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

h1, h2, h3, h4 {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -0.02em;
}

code, .stCode, pre {
    font-family: 'IBM Plex Mono', 'SF Mono', monospace !important;
}

/* ── App header ─────────────────────────────────────────────── */
.app-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 0;
    margin-bottom: 4px;
}
.app-header span:first-child { flex-shrink: 0; }
.app-header .title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #f5f5f5;
    letter-spacing: -0.01em;
}

.subtitle {
    color: #8a8a8a;
    font-size: 0.88rem;
    margin-top: -0.25rem;
    margin-bottom: 1rem;
}

/* ── Cards ──────────────────────────────────────────────────── */
.card {
    background: #1e1e1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 12px;
}

.card-emerald {
    background: rgba(16,185,129,0.05);
    border: 1px solid rgba(16,185,129,0.4);
}

.card-amber {
    background: rgba(245,158,11,0.05);
    border: 1px solid rgba(245,158,11,0.4);
}

.card-dashed {
    border: 1px dashed rgba(255,255,255,0.15);
    background: transparent;
    text-align: center;
    color: #6b6b6b;
}

/* ── Section titles ─────────────────────────────────────────── */
.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    color: #d4d4d4;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 10px;
    margin-top: 20px;
}

/* ── Badges ─────────────────────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    border: 1px solid;
    white-space: nowrap;
}

.badge-sm {
    padding: 1px 7px;
    font-size: 0.7rem;
    border-radius: 4px;
}

/* ── Confidence delta ───────────────────────────────────────── */
.delta-pos { color: #34d399; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; font-weight: 500; }
.delta-neg { color: #fb7185; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; font-weight: 500; }

/* ── Classification complete card ───────────────────────────── */
.complete-header { display: flex; align-items: center; gap: 12px; }
.complete-icon {
    width: 40px; height: 40px; border-radius: 50%;
    background: rgba(16,185,129,0.15);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    color: #34d399;
}
.complete-title { font-size: 0.85rem; font-weight: 600; color: #34d399; }
.complete-subtitle { font-size: 0.75rem; color: #8a8a8a; }
.complete-row {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 14px;
}
.complete-pct {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.6rem; font-weight: 700; color: #34d399;
    letter-spacing: -0.02em;
}
.complete-meta { display: flex; align-items: center; gap: 6px; color: #8a8a8a; font-size: 0.75rem; margin-top: 10px; }
.complete-audit { font-size: 0.78rem; color: #8a8a8a; margin-top: 10px; line-height: 1.5; }

/* ── Workflow step cards ────────────────────────────────────── */
.wf-card {
    background: #1e1e1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 8px;
}
.wf-card.active { border-color: rgba(52,211,153,0.5); box-shadow: 0 0 8px rgba(52,211,153,0.1); }
.wf-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wf-qnum {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
    background: rgba(255,255,255,0.08); color: #d4d4d4;
    padding: 2px 8px; border-radius: 4px; font-weight: 500;
}
.wf-stage { font-size: 0.78rem; color: #8a8a8a; }
.wf-status-icon {
    width: 20px; height: 20px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    margin-left: auto; flex-shrink: 0;
}
.wf-status-complete { background: rgba(16,185,129,0.15); color: #34d399; }
.wf-status-active { background: rgba(52,211,153,0.15); color: #34d399; }
.wf-action {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.8rem; color: #d4d4d4; margin-top: 10px;
}
.wf-action span:first-child { color: #8a8a8a; }
.wf-tool {
    margin-top: 8px; padding: 8px 12px; border-radius: 6px;
    border: 1px dashed rgba(255,255,255,0.12); background: rgba(255,255,255,0.03);
    display: flex; align-items: center; gap: 8px; font-size: 0.78rem; color: #8a8a8a;
}
.wf-finding {
    margin-top: 10px; padding: 10px 14px; border-radius: 6px;
    background: rgba(16,185,129,0.05); border: 1px solid rgba(16,185,129,0.2);
    font-size: 0.8rem; color: rgba(52,211,153,0.8); line-height: 1.5;
}

/* ── Evidence cards ─────────────────────────────────────────── */
.ev-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
}
.ev-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.ev-title { display: flex; align-items: center; gap: 6px; font-size: 0.82rem; font-weight: 500; color: #d4d4d4; }
.ev-title span:first-child { color: #8a8a8a; }
.ev-signal { font-size: 0.65rem; padding: 1px 6px; border-radius: 4px; border: 1px solid; font-weight: 500; }
.ev-signal-strong { background: rgba(16,185,129,0.15); color: #34d399; border-color: rgba(16,185,129,0.3); }
.ev-signal-partial { background: rgba(245,158,11,0.15); color: #fbbf24; border-color: rgba(245,158,11,0.3); }
.ev-signal-weak { background: rgba(100,116,139,0.15); color: #94a3b8; border-color: rgba(100,116,139,0.3); }
.ev-meta { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; font-size: 0.75rem; color: #8a8a8a; margin-top: 8px; }
.ev-meta dt { font-weight: 500; }
.ev-content { font-size: 0.75rem; color: #8a8a8a; margin-top: 8px; line-height: 1.5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }

/* ── Reasoning chain ────────────────────────────────────────── */
.rs-card {
    background: #1e1e1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 6px;
}
.rs-header { display: flex; align-items: center; gap: 8px; }
.rs-num {
    width: 24px; height: 24px; border-radius: 50%;
    background: rgba(255,255,255,0.06); color: #d4d4d4;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 500; flex-shrink: 0;
}
.rs-inference { font-size: 0.85rem; color: #d4d4d4; margin-top: 8px; line-height: 1.5; }
.rs-evidence { font-size: 0.75rem; color: #8a8a8a; margin-top: 4px; }

/* ── Operator review header ─────────────────────────────────── */
.op-header { display: flex; align-items: center; gap: 12px; }
.op-icon {
    width: 40px; height: 40px; border-radius: 50%;
    background: rgba(245,158,11,0.15);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; color: #fbbf24;
}
.op-title { font-size: 0.85rem; font-weight: 600; color: #fbbf24; }
.op-subtitle { font-size: 0.75rem; color: #8a8a8a; }
.op-reasons { margin-top: 12px; padding-left: 0; list-style: none; }
.op-reasons li {
    display: flex; align-items: flex-start; gap: 8px;
    font-size: 0.78rem; color: #8a8a8a; margin-bottom: 4px;
}
.op-reasons li::before {
    content: '';
    width: 5px; height: 5px; border-radius: 50%;
    background: rgba(245,158,11,0.6);
    margin-top: 6px; flex-shrink: 0;
}

/* ── Decision logic card ────────────────────────────────────── */
.dl-header { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; font-weight: 500; color: #d4d4d4; margin-bottom: 12px; }
.dl-header span:first-child { color: #8a8a8a; }
.dl-row { display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; padding: 3px 0; }
.dl-source { color: #8a8a8a; }
.dl-separator { border-top: 1px solid rgba(255,255,255,0.06); margin: 10px 0; }
.dl-factor { display: flex; align-items: flex-start; gap: 6px; font-size: 0.78rem; color: #d4d4d4; margin-bottom: 4px; }
.dl-dot { width: 6px; height: 6px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.dl-dot-pos { background: #34d399; }
.dl-dot-neg { background: #fb7185; }

/* ── Detail header bar ──────────────────────────────────────── */
.detail-bar {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 12px;
    padding: 10px 16px; border-radius: 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 12px;
}
.detail-bar-left { font-size: 0.82rem; color: #d4d4d4; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 50%; }
.detail-bar-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; flex-wrap: wrap; }
.detail-bar-stat { display: flex; align-items: center; gap: 4px; font-size: 0.78rem; color: #8a8a8a; }
.detail-bar-stat span:first-child { color: #8a8a8a; }
.detail-bar-conf { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 0.85rem; color: #d4d4d4; }

/* ── Example cards ──────────────────────────────────────────── */
.ex-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 8px; }
@media (max-width: 768px) { .ex-grid { grid-template-columns: 1fr; } }
.ex-card {
    background: #1e1e1e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 14px; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
}
.ex-card:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.15); }
.ex-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.ex-name { font-size: 0.82rem; font-weight: 500; color: #d4d4d4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ex-issuer { font-size: 0.75rem; color: #8a8a8a; margin-bottom: 4px; }
.ex-desc { font-size: 0.75rem; color: #6b6b6b; line-height: 1.4; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

/* ── Misc ───────────────────────────────────────────────────── */
.muted { color: #8a8a8a; font-size: 0.85rem; }
.mono { font-family: 'IBM Plex Mono', monospace; }
.divider { border-top: 1px solid rgba(255,255,255,0.06); margin: 16px 0; }

/* ── Streamlit overrides ────────────────────────────────────── */

/* Tabs: proper spacing, no overlap */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 500;
    font-size: 0.88rem;
    padding: 10px 20px;
    border-radius: 6px 6px 0 0;
    white-space: nowrap;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #34d399 !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none;
}

/* Forms */
div[data-testid="stForm"] {
    background: #1e1e1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 20px;
}

/* Expanders */
div[data-testid="stExpander"] {
    background: #1e1e1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
}

/* Containers with border */
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-color: rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
}

/* Metrics */
div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
}

/* Hide default streamlit header */
header[data-testid="stHeader"] {
    background: rgba(20,20,20,0.9) !important;
    backdrop-filter: blur(10px);
}

/* Main block spacing */
.block-container {
    padding-top: 2rem !important;
    max-width: 1200px;
}
</style>
"""
