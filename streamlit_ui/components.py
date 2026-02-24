"""Reusable HTML component builders for the Streamlit UI.

Every public function returns an HTML string to be rendered via
``st.markdown(html, unsafe_allow_html=True)``.
"""

from __future__ import annotations

import html as _html
from typing import Any

try:
    from streamlit_ui.styles import (
        CATEGORY_CODES,
        CATEGORY_COLORS,
        DIFFICULTY_COLORS,
        ICON_ALERT,
        ICON_BOOK_OPEN,
        ICON_CHECK,
        ICON_CLOCK,
        ICON_SCALE,
        ICON_SEARCH,
        ICON_SHIELD,
        ICON_TRENDING_UP,
        SOURCE_COLORS,
        SOURCE_ICONS,
        STAGE_LABELS,
    )
except ModuleNotFoundError:  # pragma: no cover
    from styles import (  # type: ignore[no-redef]
        CATEGORY_CODES,
        CATEGORY_COLORS,
        DIFFICULTY_COLORS,
        ICON_ALERT,
        ICON_BOOK_OPEN,
        ICON_CHECK,
        ICON_CLOCK,
        ICON_SCALE,
        ICON_SEARCH,
        ICON_SHIELD,
        ICON_TRENDING_UP,
        SOURCE_COLORS,
        SOURCE_ICONS,
        STAGE_LABELS,
    )


def _esc(text: Any) -> str:
    return _html.escape(str(text)) if text else ""


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "0%"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def header_html() -> str:
    return f"""
    <div class="app-header">
        {ICON_SHIELD}
        <span class="title">Automated Asset Classification</span>
    </div>
    <div class="subtitle">
        Classify private securities with auditable reasoning, live evidence
        tracking, and operator review controls.
    </div>
    """


# ---------------------------------------------------------------------------
# Category badge
# ---------------------------------------------------------------------------
def category_badge_html(category: str) -> str:
    colors = CATEGORY_COLORS.get(category, CATEGORY_COLORS["other"])
    code_info = CATEGORY_CODES.get(category, ("A99", "Unclassified"))
    return (
        f'<span class="badge" style="background:{colors.bg};color:{colors.text};'
        f'border-color:{colors.border}">'
        f"{_esc(code_info[0])} &mdash; {_esc(code_info[1])}</span>"
    )


# ---------------------------------------------------------------------------
# Confidence delta
# ---------------------------------------------------------------------------
def delta_html(delta: float | None) -> str:
    if delta is None or delta == 0:
        return ""
    cls = "delta-pos" if delta > 0 else "delta-neg"
    sign = "+" if delta > 0 else ""
    return f'<span class="{cls}">{sign}{delta:.2f}</span>'


# ---------------------------------------------------------------------------
# Detail header bar
# ---------------------------------------------------------------------------
def detail_header_html(
    description: str,
    result: dict[str, Any] | None,
    elapsed: float,
) -> str:
    cat_badge = ""
    conf = ""
    if isinstance(result, dict):
        cat_badge = category_badge_html(str(result.get("category", "other")))
        conf = f'<span class="detail-bar-conf">{_pct(result.get("confidence", 0))}</span>'

    return f"""
    <div class="detail-bar">
        <div class="detail-bar-left" title="{_esc(description)}">{_esc(description[:80])}</div>
        <div class="detail-bar-right">
            {cat_badge}
            <span class="detail-bar-stat">{ICON_TRENDING_UP} {conf}</span>
            <span class="detail-bar-stat">{ICON_CLOCK} <span class="mono">{elapsed:.1f}s</span></span>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Classification complete card
# ---------------------------------------------------------------------------
def classification_complete_html(
    category: str,
    confidence: float,
    audit_comment: str | None = None,
    duration: float | None = None,
) -> str:
    badge = category_badge_html(category)
    pct = f"{confidence * 100:.0f}%"
    audit = f'<div class="complete-audit">{_esc(audit_comment)}</div>' if audit_comment else ""
    dur = (
        f'<div class="complete-meta">{ICON_CLOCK} Completed in {duration:.1f}s</div>'
        if duration is not None
        else ""
    )
    return f"""
    <div class="card card-emerald">
        <div class="complete-header">
            <div class="complete-icon">{ICON_CHECK}</div>
            <div>
                <div class="complete-title">Classification Complete</div>
                <div class="complete-subtitle">Pipeline finished successfully</div>
            </div>
        </div>
        <div class="complete-row">
            {badge}
            <span class="complete-pct">{pct}</span>
        </div>
        {audit}
        {dur}
    </div>
    """


# ---------------------------------------------------------------------------
# Workflow step card
# ---------------------------------------------------------------------------
def workflow_step_html(
    q_num: int,
    stage_name: str,
    action_detail: str | None,
    finding: str | None,
    confidence_delta: float | None,
    status: str,
    tool_name: str | None = None,
    data_source: str | None = None,
) -> str:
    active_cls = " active" if status == "active" else ""
    status_icon_cls = "wf-status-complete" if status == "complete" else "wf-status-active"
    status_icon = ICON_CHECK if status == "complete" else "..."

    delta = delta_html(confidence_delta)

    # Source icon
    src_icon = SOURCE_ICONS.get(str(data_source), SOURCE_ICONS.get(str(tool_name), ""))

    action_html = ""
    if action_detail:
        action_html = f"""
        <div class="wf-action">{ICON_SEARCH} <span>{_esc(action_detail)}</span></div>
        """

    tool_html = ""
    if tool_name or data_source:
        parts = []
        if src_icon:
            parts.append(src_icon)
        if tool_name:
            parts.append(f"<span>{_esc(tool_name)}</span>")
        if data_source:
            parts.append(f"<span style='color:#6b6b6b'>via {_esc(data_source)}</span>")
        tool_html = f'<div class="wf-tool">{"".join(parts)}</div>'

    finding_html = ""
    if finding:
        finding_html = f'<div class="wf-finding">{_esc(finding)}</div>'

    return f"""
    <div class="wf-card{active_cls}">
        <div class="wf-header">
            <span class="wf-qnum">Q{q_num}</span>
            <span class="wf-stage">{_esc(stage_name)}</span>
            {delta}
            <span class="wf-status-icon {status_icon_cls}">{status_icon}</span>
        </div>
        {action_html}
        {tool_html}
        {finding_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Stage label
# ---------------------------------------------------------------------------
def stage_label_html(stage_key: str) -> str:
    label = STAGE_LABELS.get(stage_key, f"Stage {_esc(stage_key)}")
    return f'<div class="section-title" style="margin-top:16px;margin-bottom:6px">{_esc(label)}</div>'


# ---------------------------------------------------------------------------
# Evidence card
# ---------------------------------------------------------------------------
def evidence_card_html(
    source_type: str,
    source_detail: str,
    content: str,
    relevance: str,
) -> str:
    icon = SOURCE_ICONS.get(source_type, "")
    signal_cls = "ev-signal-strong"
    if relevance.lower() in ("partial", "medium"):
        signal_cls = "ev-signal-partial"
    elif relevance.lower() in ("weak", "low"):
        signal_cls = "ev-signal-weak"

    return f"""
    <div class="ev-card">
        <div class="ev-header">
            <span class="ev-title">{icon} {_esc(source_type)}</span>
            <span class="ev-signal {signal_cls}">{_esc(relevance)}</span>
        </div>
        <dl class="ev-meta">
            <dt>Source</dt><dd>{_esc(source_detail)}</dd>
        </dl>
        <div class="ev-content">{_esc(content)}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# Reasoning step card
# ---------------------------------------------------------------------------
def reasoning_step_html(
    step_num: int,
    source: str,
    confidence_delta: float | None,
    inference: str,
    evidence: str | None = None,
) -> str:
    src_colors = SOURCE_COLORS.get(source, ("rgba(255,255,255,0.06)", "#94a3b8"))
    src_badge = (
        f'<span class="badge badge-sm" style="background:{src_colors[0]};'
        f'color:{src_colors[1]};border-color:transparent">{_esc(source)}</span>'
    )
    delta = delta_html(confidence_delta)
    ev_html = f'<div class="rs-evidence">Evidence: {_esc(evidence)}</div>' if evidence else ""

    return f"""
    <div class="rs-card">
        <div class="rs-header">
            <span class="rs-num">{step_num}</span>
            {src_badge}
            <span style="margin-left:auto">{delta}</span>
        </div>
        <div class="rs-inference">{_esc(inference)}</div>
        {ev_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Operator review header
# ---------------------------------------------------------------------------
def operator_review_header_html(uncertainty_reasons: list[str]) -> str:
    reasons_html = ""
    if uncertainty_reasons:
        items = "".join(f"<li>{_esc(r)}</li>" for r in uncertainty_reasons)
        reasons_html = f'<ul class="op-reasons">{items}</ul>'

    return f"""
    <div class="card card-amber">
        <div class="op-header">
            <div class="op-icon">{ICON_ALERT}</div>
            <div>
                <div class="op-title">Operator Review Required</div>
                <div class="op-subtitle">Classification confidence below threshold</div>
            </div>
        </div>
        {reasons_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Decision logic card
# ---------------------------------------------------------------------------
def decision_logic_html(
    result: dict[str, Any] | None,
    confidence_history: list[dict[str, Any]],
) -> str:
    if not isinstance(result, dict) and not confidence_history:
        return ""

    # Build-up rows
    rows = ""
    for point in confidence_history:
        source = str(point.get("category", ""))
        score = float(point.get("score", 0))
        step = point.get("step", "?")
        rows += f"""
        <div class="dl-row">
            <span class="dl-source">Step {step} &middot; {_esc(source)}</span>
            <span class="mono" style="color:#d4d4d4">{score*100:.0f}%</span>
        </div>
        """

    # Key factors from result reasoning
    factors = ""
    if isinstance(result, dict):
        reasoning = result.get("reasoning", [])
        if isinstance(reasoning, list):
            factor_items = ""
            for step in reasoning[:5]:
                if isinstance(step, dict):
                    delta = step.get("confidence_delta", 0)
                    dot_cls = "dl-dot-pos" if (isinstance(delta, (int, float)) and delta >= 0) else "dl-dot-neg"
                    inference = str(step.get("inference", ""))
                    factor_items += f"""
                    <div class="dl-factor">
                        <span class="dl-dot {dot_cls}"></span>
                        <span>{_esc(inference[:120])}</span>
                    </div>
                    """
            if factor_items:
                factors = f"""
                <div class="dl-separator"></div>
                <div style="display:flex;align-items:center;gap:6px;font-size:0.78rem;font-weight:500;color:#d4d4d4;margin-bottom:8px">
                    {ICON_BOOK_OPEN} Key Decision Factors
                </div>
                {factor_items}
                """

    # Audit comment
    audit = ""
    if isinstance(result, dict) and result.get("audit_comment"):
        audit = f"""
        <div class="dl-separator"></div>
        <div style="font-size:0.75rem;font-style:italic;color:rgba(138,138,138,0.8)">
            {_esc(result["audit_comment"])}
        </div>
        """

    cat_badge = ""
    if isinstance(result, dict):
        cat_badge = category_badge_html(str(result.get("category", "other")))

    return f"""
    <div class="card">
        <div class="dl-header">{ICON_SCALE} Decision Logic</div>
        {cat_badge}
        <div class="dl-separator"></div>
        <div style="font-size:0.78rem;font-weight:500;color:#d4d4d4;margin-bottom:6px">Confidence Build-up</div>
        {rows}
        {factors}
        {audit}
    </div>
    """


# ---------------------------------------------------------------------------
# Example cards
# ---------------------------------------------------------------------------
def example_cards_html(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""

    cards = ""
    for ex in examples:
        name = _esc(ex.get("name", ""))
        issuer = _esc(ex.get("issuer", ""))
        desc = _esc(str(ex.get("description", ""))[:120])
        diff = str(ex.get("difficulty", "medium"))
        diff_colors = DIFFICULTY_COLORS.get(diff, DIFFICULTY_COLORS["medium"])
        diff_badge = (
            f'<span class="badge badge-sm" style="background:{diff_colors[0]};'
            f'color:{diff_colors[1]};border-color:transparent">{_esc(diff)}</span>'
        )
        cards += f"""
        <div class="ex-card" data-desc="{_esc(ex.get('description', ''))}">
            <div class="ex-top">
                <span class="ex-name">{name}</span>
                {diff_badge}
            </div>
            <div class="ex-issuer">{issuer}</div>
            <div class="ex-desc">{desc}</div>
        </div>
        """

    return f"""
    <div style="font-size:0.82rem;color:#8a8a8a;margin-top:8px">Or try an example:</div>
    <div class="ex-grid">{cards}</div>
    """


# ---------------------------------------------------------------------------
# Placeholder (dashed card)
# ---------------------------------------------------------------------------
def placeholder_html(title: str, subtitle: str = "") -> str:
    sub = f'<div style="font-size:0.72rem;color:#555;margin-top:4px">{_esc(subtitle)}</div>' if subtitle else ""
    return f"""
    <div class="card card-dashed">
        <div style="font-size:0.82rem">{_esc(title)}</div>
        {sub}
    </div>
    """
