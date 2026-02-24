# Streamlit UI: Match Next.js App Design

**Date:** 2026-02-24
**Status:** Approved

## Goal

Rewrite the Streamlit frontend (`streamlit_ui/`) to match the Next.js app's visual design, layout, and component structure. The result should be a "full match and better" - same dark theme aesthetic, same card-based layout, same color-coded categories, and same component hierarchy.

## Architecture

### New Files

- `streamlit_ui/styles.py` - All CSS constants and HTML template functions
- `streamlit_ui/components.py` - Reusable HTML component builders (badges, cards, icons)
- `.streamlit/config.toml` - Streamlit dark theme configuration

### Modified Files

- `streamlit_ui/app.py` - Complete rewrite of render functions using new components

### Unchanged Files

- `streamlit_ui/api_client.py` - No changes needed
- `streamlit_ui/controller.py` - No changes needed
- `streamlit_ui/state.py` - No changes needed
- `streamlit_ui/sse_parser.py` - No changes needed

## Design Details

### 1. Dark Theme (config.toml)

Match Next.js dark mode:
- Background: `#1a1a1a` (oklch 0.145)
- Card/secondary: `#2d2d2d` (oklch 0.205)
- Text: `#f5f5f5` (oklch 0.985)
- Primary: emerald green accent
- Muted text: `#8a8a8a` (oklch 0.556)
- Border: `rgba(255,255,255,0.1)`

### 2. CSS System (styles.py)

Category colour map (matches Next.js CATEGORY_COLORS):
- equity: blue (bg `rgba(59,130,246,0.15)`, text `#60a5fa`)
- debt: amber (bg `rgba(245,158,11,0.15)`, text `#fbbf24`)
- convertible_note: violet (bg `rgba(139,92,246,0.15)`, text `#a78bfa`)
- safe: emerald (bg `rgba(16,185,129,0.15)`, text `#34d399`)
- fund_interest: cyan (bg `rgba(6,182,212,0.15)`, text `#22d3ee`)
- real_estate: orange (bg `rgba(249,115,22,0.15)`, text `#fb923c`)
- revenue_share: rose (bg `rgba(244,63,94,0.15)`, text `#fb7185`)
- other: slate (bg `rgba(100,116,139,0.15)`, text `#94a3b8`)

Category codes (matches CATEGORY_CODES):
- equity: A01 Equity Securities
- debt: A02 Debt Securities
- convertible_note: A03 Convertible Notes
- safe: A04 SAFE Instruments
- real_estate: A05 Real Estate Securities
- revenue_share: A06 Revenue Participation
- fund_interest: A08 Private Equity Funds
- other: A99 Unclassified

### 3. Components (components.py)

HTML builder functions returning `st.markdown(html, unsafe_allow_html=True)`:

- `render_header()` - Shield SVG icon + title + subtitle in sticky header
- `render_category_badge(category)` - Colour-coded badge with code + label
- `render_confidence_badge(score)` - Monospace percentage with colour
- `render_confidence_delta(delta)` - Green (+) or red (-) delta badge
- `render_example_card(name, issuer, description, difficulty)` - Clickable card
- `render_classification_complete(category, confidence, audit_comment, duration)` - Emerald success card
- `render_workflow_step(q_num, stage, action, finding, tool, source, delta, status)` - Investigation step card
- `render_evidence_card(source_type, source_detail, content, relevance)` - Evidence with signal badge
- `render_reasoning_step(step_num, source, delta, inference, evidence)` - Reasoning chain step
- `render_operator_review_header(uncertainty_reasons)` - Amber warning card header
- `render_decision_logic(result, confidence_history)` - Decision factors card
- `render_detail_header(description, result, elapsed)` - Status bar with badges

### 4. Layout Structure (app.py)

```
Header (HTML)
Tabs: [Workspace] [Review Queue] [History]

Workspace tab:
  2-column grid (col_ratio 3:2)
  Left column:
    - Classification Input Card (form in styled card)
    - Example Cards Grid (fetched from /api/examples, 3-col grid)
    - Detail Header Bar (when running/complete)
    - Workflow Timeline (investigation step cards)
    - Reasoning Chain (numbered step cards)
    - Classification Result (emerald complete card or dashed placeholder)
    - Operator Review (amber card with actions)
    - Agree/Disagree + Inline Feedback
  Right column:
    - Confidence Chart (Plotly - dark theme, emerald line, threshold line)
    - Evidence Cards (with signal strength badges)
    - Decision Logic Card

Review Queue tab:
  - Refresh button
  - Queue items as styled cards with inline review forms

History tab:
  - Refresh button
  - Styled data table
  - Record inspector
```

### 5. Confidence Chart (Plotly)

Replace `st.line_chart` with `st.plotly_chart`:
- Dark background (`#1a1a1a`)
- Emerald line (`#34d399`) with dots
- Dashed threshold reference line at configured threshold
- X-axis: step numbers
- Y-axis: 0-100% range
- Tooltips showing score + category
- No gridlines, minimal axes

### 6. Example Cards

New feature - fetch from `/api/examples`:
- 3-column grid of clickable cards
- Each shows: name, issuer, description (2-line clamp), difficulty badge
- Difficulty colours: easy=emerald, medium=amber, hard=rose
- On click: populate textarea + auto-submit

## Dependencies

- `plotly` - for confidence chart (add to pyproject.toml)
- No other new dependencies needed

## Constraints

- All HTML rendering via `st.markdown(html, unsafe_allow_html=True)` or `st.html()`
- Keep the same backend API contract (no backend changes)
- Preserve all existing functionality while improving appearance
- Session state keys remain the same for compatibility
