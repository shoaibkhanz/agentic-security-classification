"""Streamlit frontend — matches the Next.js app's dark-theme aesthetic."""

from __future__ import annotations

import os
from typing import Any

import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_ui.api_client import StreamlitAPIClient
    from streamlit_ui.components import (
        category_badge_html,
        header_html,
    )
    from streamlit_ui.controller import run_classification_stream
    from streamlit_ui.state import ClassificationSnapshot
    from streamlit_ui.styles import (
        CATEGORY_OPTIONS,
        get_stylesheet,
    )
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from api_client import StreamlitAPIClient  # type: ignore[no-redef]
    from components import (  # type: ignore[no-redef]
        category_badge_html,
        header_html,
    )
    from controller import run_classification_stream  # type: ignore[no-redef]
    from state import ClassificationSnapshot  # type: ignore[no-redef]
    from styles import (  # type: ignore[no-redef]
        CATEGORY_OPTIONS,
        get_stylesheet,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Page config  (must be first Streamlit call)
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Automated Asset Classification",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def _as_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _empty_snapshot() -> ClassificationSnapshot:
    return ClassificationSnapshot()


def _ensure_state() -> None:
    defaults: dict[str, Any] = {
        "description_input": "",
        "additional_context": "",
        "confidence_threshold": 0.82,
        "demo_mode": True,  # always use demo streaming
        "api_base_url": os.getenv("CLASSIFIER_API_BASE_URL", "http://localhost:8000"),
        "snapshot": _empty_snapshot(),
        "history_rows": [],
        "queue_rows": [],
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Apply pending description from example card clicks.
    # This must happen BEFORE any widget with key="description_input" is created.
    if st.session_state.get("_pending_description") is not None:
        st.session_state.description_input = st.session_state._pending_description
        del st.session_state._pending_description


def _client() -> StreamlitAPIClient:
    return StreamlitAPIClient(base_url=st.session_state.api_base_url)


# ═══════════════════════════════════════════════════════════════════════════
# Classification runner
# ═══════════════════════════════════════════════════════════════════════════
def _render_live_metrics(snapshot: ClassificationSnapshot, slot: Any) -> None:
    with slot.container():
        col_a, col_b, col_c = st.columns(3)
        latest_conf = snapshot.confidence_history[-1] if snapshot.confidence_history else {}
        col_a.metric("Events", len(snapshot.events))
        col_b.metric("Category", str(latest_conf.get("category", "-")))
        col_c.metric("Confidence", _as_pct(latest_conf.get("score", 0.0)))


# Only these node_start events get shown to the user
_VISIBLE_NODES: dict[str, str] = {
    "InitialAssessment": "Assessing security description",
    "Classify": "Making classification decision",
    "Verify": "Verifying result",
}


def _run_classification(client: StreamlitAPIClient) -> None:
    progress = st.progress(0, text="Starting classification...")
    status_slot = st.empty()
    metrics_slot = st.empty()
    evidence_count = 0

    def on_event(snapshot: ClassificationSnapshot, event: dict[str, object]) -> None:
        nonlocal evidence_count
        event_type = str(event.get("event_type", "unknown"))
        node_name = str(event.get("node_name") or "")
        node_starts = [e for e in snapshot.events if e.get("event_type") == "node_start"]
        pct = min(96, 8 + len(node_starts) * 14)

        # Determine what to show
        label = None
        if event_type == "node_start" and node_name in _VISIBLE_NODES:
            label = _VISIBLE_NODES[node_name]
        elif event_type == "evidence_found":
            evidence_count += 1
            label = f"Researching evidence ({evidence_count})"
        elif event_type == "result":
            label = "Result ready"

        if label:
            progress.progress(pct, text=label)
            status_slot.caption(label + "...")

        _render_live_metrics(snapshot, metrics_slot)

    try:
        snapshot = run_classification_stream(
            client=client,
            description=st.session_state.description_input,
            additional_context=st.session_state.additional_context or None,
            confidence_threshold=float(st.session_state.confidence_threshold),
            demo=bool(st.session_state.demo_mode),
            on_event=on_event,
        )
    except Exception as exc:
        progress.progress(100, text="Connection failed")
        status_slot.empty()
        st.error(
            f"Could not connect to the backend at **{st.session_state.api_base_url}**.\n\n"
            f"Start it with: `uv run uvicorn web.api.main:app --reload --port 8000`\n\n"
            f"Error: `{exc}`"
        )
        # Reset snapshot so placeholder sections don't appear
        st.session_state.snapshot = _empty_snapshot()
        return

    st.session_state.snapshot = snapshot

    if snapshot.status == "complete":
        progress.progress(100, text="Classification complete")
        status_slot.empty()
    elif snapshot.error:
        progress.progress(100, text="Failed")
        status_slot.empty()
        st.error(
            f"Classification failed: {snapshot.error}\n\n"
            f"Make sure the backend is running: "
            f"`uv run uvicorn web.api.main:app --reload --port 8000`"
        )
    else:
        progress.progress(100, text="Failed")
        status_slot.empty()


# ═══════════════════════════════════════════════════════════════════════════
# Confidence chart  (Plotly)
# ═══════════════════════════════════════════════════════════════════════════
def _render_confidence_chart(snapshot: ClassificationSnapshot) -> None:
    if not snapshot.confidence_history:
        st.caption("Confidence trend populates when scoring updates stream in.")
        return

    steps = [int(p.get("step", i + 1)) for i, p in enumerate(snapshot.confidence_history)]
    scores = [float(p.get("score", 0)) * 100 for p in snapshot.confidence_history]
    categories = [str(p.get("category", "")) for p in snapshot.confidence_history]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=scores,
            mode="lines+markers",
            line={"color": "#34d399", "width": 2},
            marker={"size": 7, "color": "#34d399"},
            customdata=categories,
            hovertemplate="Step %{x}<br>Score: %{y:.1f}%<br>Category: %{customdata}<extra></extra>",
        )
    )
    # Threshold reference line
    threshold = float(st.session_state.confidence_threshold) * 100
    fig.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="rgba(255,255,255,0.2)",
        annotation_text=f"Threshold {threshold:.0f}%",
        annotation_position="bottom right",
        annotation_font_color="rgba(255,255,255,0.3)",
        annotation_font_size=10,
    )
    fig.update_layout(
        height=220,
        margin={"t": 10, "b": 30, "l": 40, "r": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={
            "title": None,
            "showgrid": False,
            "color": "rgba(255,255,255,0.3)",
            "dtick": 1,
        },
        yaxis={
            "title": None,
            "range": [0, 105],
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,0.04)",
            "color": "rgba(255,255,255,0.3)",
            "ticksuffix": "%",
        },
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)

    # Latest score caption
    latest = snapshot.confidence_history[-1]
    cat = str(latest.get("category", "unknown"))
    score = _as_pct(latest.get("score", 0))
    st.markdown(
        f'<div style="font-size:0.78rem;color:#8a8a8a;margin-top:-8px">'
        f"Latest: <b>{cat}</b> at <b>{score}</b></div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Workspace tab — Input panel
# ═══════════════════════════════════════════════════════════════════════════
def _render_input_panel(client: StreamlitAPIClient) -> None:
    st.markdown(
        '<div class="section-title">Classification Input</div>',
        unsafe_allow_html=True,
    )
    with st.form("run_form", clear_on_submit=False):
        st.text_area(
            "Security description",
            key="description_input",
            height=140,
            placeholder=(
                "Example: Atlas Senior Secured Notes due 2028, 8.5% fixed coupon, "
                "first-lien collateral over infrastructure assets, issued by "
                "Atlas Infrastructure Holdings."
            ),
            help="Include instrument type, issuer, terms, and any collateral or conversion features.",
        )

        st.markdown(
            '<span style="font-size:0.72rem;color:#555">Press Cmd/Ctrl + Enter to submit</span>',
            unsafe_allow_html=True,
        )

        st.text_area(
            "Analyst context (optional)",
            key="additional_context",
            height=80,
            placeholder="Optional correction or context to guide this run.",
        )

        st.session_state.confidence_threshold = st.slider(
            "Confidence threshold",
            min_value=0.50,
            max_value=1.00,
            value=float(st.session_state.confidence_threshold),
            step=0.01,
        )

        submitted = st.form_submit_button(
            "Run Classification",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        text = st.session_state.description_input.strip()
        if len(text) < 5:
            st.warning(f"Enter at least 5 characters to classify (currently {len(text)}).")
        else:
            _run_classification(client)


# ═══════════════════════════════════════════════════════════════════════════
# Workspace tab — Result
# ═══════════════════════════════════════════════════════════════════════════
def _render_result(snapshot: ClassificationSnapshot) -> None:
    st.markdown("**Classification Result**")

    if not isinstance(snapshot.result, dict):
        st.caption("Final classification will appear here.")
        return

    result = snapshot.result
    category = str(result.get("category", "other"))
    confidence = float(result.get("confidence", 0))

    st.success("Classification Complete — Pipeline finished successfully")
    st.markdown(
        category_badge_html(category),
        unsafe_allow_html=True,
    )
    st.metric("Confidence", f"{confidence * 100:.0f}%")

    if result.get("audit_comment"):
        st.info(str(result["audit_comment"]))

    if snapshot.elapsed_seconds > 0:
        st.caption(f"Completed in {snapshot.elapsed_seconds:.1f}s")

    # Summary
    summary = result.get("summary")
    if summary:
        st.markdown(str(summary))

    # Uncertainty reasons
    uncertainty = result.get("uncertainty_reasons", [])
    if isinstance(uncertainty, list) and uncertainty:
        st.caption("Uncertainty notes:")
        for reason in uncertainty:
            st.markdown(f"- {reason}")


# ═══════════════════════════════════════════════════════════════════════════
# Workspace tab — Workflow timeline
# ═══════════════════════════════════════════════════════════════════════════
def _render_workflow(snapshot: ClassificationSnapshot) -> None:
    st.markdown("**Investigation Workflow**")

    if not snapshot.workflow_stages:
        st.caption("Workflow steps will appear once events start streaming.")
        return

    for stage_group in snapshot.workflow_stages:
        stage_key = str(stage_group.get("stage", ""))
        st.caption(stage_key.replace("_", " ").title() if stage_key else "Stage")

        questions = stage_group.get("questions", [])
        for q in questions:
            q_num = int(q.get("questionNumber", 0))
            stage_name = str(q.get("stageName", ""))
            action = q.get("actionDetail") or ""
            finding = q.get("finding") or ""
            status = str(q.get("status", "pending"))
            delta = q.get("confidenceDelta")
            icon = "✓" if status == "complete" else "..."
            delta_str = ""
            if isinstance(delta, (int, float)) and delta != 0:
                sign = "+" if delta > 0 else ""
                delta_str = f" ({sign}{delta:.2f})"
            with st.container(border=True):
                st.markdown(f"{icon} **Q{q_num}** {stage_name}{delta_str}")
                if action:
                    st.caption(action)
                if finding:
                    st.markdown(f"_{finding}_")


# ═══════════════════════════════════════════════════════════════════════════
# Workspace tab — Reasoning chain
# ═══════════════════════════════════════════════════════════════════════════
def _render_reasoning(snapshot: ClassificationSnapshot) -> None:
    st.markdown("**Execution Details**")

    if not snapshot.execution_details:
        st.caption("Reasoning details appear as evidence accumulates.")
        return

    for step in snapshot.execution_details:
        delta = step.get("confidence_delta")
        if isinstance(delta, str):
            try:
                delta = float(delta)
            except ValueError:
                delta = None
        step_num = int(step.get("step", 0))
        source = str(step.get("source", "workflow"))
        inference = str(step.get("inference", ""))
        evidence = step.get("evidence")
        delta_str = ""
        if isinstance(delta, (int, float)) and delta != 0:
            sign = "+" if delta > 0 else ""
            delta_str = f" ({sign}{delta:.2f})"
        with st.container(border=True):
            st.markdown(f"**{step_num}.** {source}{delta_str}")
            st.markdown(inference)
            if evidence:
                st.caption(f"Evidence: {evidence}")


# ═══════════════════════════════════════════════════════════════════════════
# Workspace tab — Operator review
# ═══════════════════════════════════════════════════════════════════════════
def _render_operator_actions(
    client: StreamlitAPIClient,
    snapshot: ClassificationSnapshot,
) -> None:
    st.markdown("**Operator Review**")

    record_id = snapshot.record_id or ""
    is_complete = snapshot.status == "complete"
    result = snapshot.result

    if not is_complete:
        st.caption("Approve, reject, or override the classification. Available after classification completes.")
        return

    # Show operator review header if needed
    needs_review = isinstance(result, dict) and result.get("needs_operator_review")
    if needs_review and isinstance(result, dict):
        uncertainty = result.get("uncertainty_reasons", [])
        if isinstance(uncertainty, list) and uncertainty:
            st.warning("**Operator Review Required** — Classification confidence below threshold")
            for reason in uncertainty:
                st.markdown(f"- {reason}")

    if not record_id:
        st.caption("Waiting for record to save...")
        return

    # Review form
    with st.form("operator_review_form", clear_on_submit=False):
        action = st.selectbox("Review action", ["approve", "reject", "override"])
        override_category = None
        if action == "override":
            override_category = st.selectbox("Override category", CATEGORY_OPTIONS)
        comment = st.text_input("Comment", value="")
        review_submit = st.form_submit_button("Submit review", use_container_width=True)

    if review_submit:
        try:
            client.submit_operator_review(
                record_id=record_id,
                action=action,
                override_category=override_category,
                comment=comment or None,
            )
            st.success("Operator review submitted.")
        except Exception as exc:
            st.error(f"Review submission failed: {exc}")

    # Agree/disagree + inline feedback
    col_agree, col_disagree = st.columns(2)
    with col_agree:
        if st.button("Agree", use_container_width=True):
            try:
                client.submit_feedback(record_id, "agree")
                st.success("Feedback recorded.")
            except Exception as exc:
                st.error(str(exc))
    with col_disagree:
        if st.button("Disagree", use_container_width=True):
            try:
                client.submit_feedback(record_id, "disagree")
                st.success("Feedback recorded.")
            except Exception as exc:
                st.error(str(exc))

    with st.form("inline_feedback_form", clear_on_submit=True):
        message = st.text_area("Inline feedback", value="", height=80)
        feedback_submit = st.form_submit_button("Send feedback", use_container_width=True)

    if feedback_submit and message.strip():
        try:
            client.submit_chat(record_id, message.strip())
            st.success("Inline feedback recorded.")
        except Exception as exc:
            st.error(f"Inline feedback failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Decision logic (broken into small HTML chunks)
# ═══════════════════════════════════════════════════════════════════════════
def _render_decision_logic(snapshot: ClassificationSnapshot) -> None:
    result = snapshot.result
    history = snapshot.confidence_history
    if not isinstance(result, dict) and not history:
        return

    st.markdown("**Decision Logic**")

    # Category badge
    if isinstance(result, dict):
        cat = str(result.get("category", "other"))
        st.markdown(
            category_badge_html(cat),
            unsafe_allow_html=True,
        )

    # Confidence build-up
    if history:
        st.caption("Confidence Build-up")
        for point in history:
            source = str(point.get("category", ""))
            score = float(point.get("score", 0))
            step = point.get("step", "?")
            st.markdown(
                f"Step {step} · {source} — **{score * 100:.0f}%**"
            )

    # Key decision factors
    if isinstance(result, dict):
        reasoning = result.get("reasoning", [])
        if isinstance(reasoning, list) and reasoning:
            st.caption("Key Decision Factors")
            for step in reasoning[:5]:
                if isinstance(step, dict):
                    delta = step.get("confidence_delta", 0)
                    sign = "+" if isinstance(delta, (int, float)) and delta >= 0 else ""
                    inference = str(step.get("inference", ""))
                    delta_str = f" ({sign}{delta:.2f})" if isinstance(delta, (int, float)) and delta != 0 else ""
                    st.markdown(f"- {inference[:120]}{delta_str}")

    # Audit comment
    if isinstance(result, dict) and result.get("audit_comment"):
        st.caption(str(result["audit_comment"]))


# ═══════════════════════════════════════════════════════════════════════════
# Evidence sidebar
# ═══════════════════════════════════════════════════════════════════════════
def _render_sidebar(snapshot: ClassificationSnapshot) -> None:
    st.markdown(
        '<div class="section-title">Evidence & Confidence</div>',
        unsafe_allow_html=True,
    )

    has_data = snapshot.status in ("complete", "error") or snapshot.events

    if not has_data:
        st.markdown(
            '<div style="color:#555;font-size:0.82rem;padding:20px 0;text-align:center">'
            "Run a classification to see confidence progression, "
            "evidence, and decision logic.</div>",
            unsafe_allow_html=True,
        )
        return

    # Confidence chart
    _render_confidence_chart(snapshot)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Evidence cards — native Streamlit to avoid HTML sanitizer issues
    if not snapshot.evidence_list:
        st.caption("Evidence feed will populate during research steps.")
    else:
        for item in snapshot.evidence_list:
            with st.container(border=True):
                source_type = str(item.get("sourceType", "unknown"))
                relevance = str(item.get("relevance", "unknown"))
                rel_color = {"strong": "#34d399", "high": "#34d399", "partial": "#fbbf24", "medium": "#fbbf24"}.get(
                    relevance.lower(), "#8a8a8a"
                )
                st.markdown(f"**{source_type}** &nbsp; <span style='color:{rel_color};font-size:0.75rem'>{relevance}</span>", unsafe_allow_html=True)
                st.caption(f"Source: {item.get('sourceDetail', '')}")
                st.markdown(str(item.get("content", ""))[:200])

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Decision logic — rendered as small chunks to avoid Streamlit HTML sanitizer
    _render_decision_logic(snapshot)


# ═══════════════════════════════════════════════════════════════════════════
# History tab
# ═══════════════════════════════════════════════════════════════════════════
def _refresh_history(client: StreamlitAPIClient) -> None:
    st.session_state.history_rows = client.fetch_history()


def _render_history_tab(client: StreamlitAPIClient) -> None:
    st.markdown(
        '<div class="section-title">Classification History</div>',
        unsafe_allow_html=True,
    )

    if st.button("Refresh history"):
        try:
            _refresh_history(client)
        except Exception as exc:
            st.error(f"History refresh failed: {exc}")

    if not st.session_state.history_rows:
        try:
            _refresh_history(client)
        except Exception as exc:
            st.error(f"History load failed: {exc}")
            return

    records = st.session_state.history_rows
    if not records:
        st.info("No history records yet.")
        return

    rows = []
    for row in records:
        if not isinstance(row, dict):
            continue
        result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
        rows.append(
            {
                "id": row.get("id", ""),
                "category": result.get("category", "unknown"),
                "confidence": _as_pct(result.get("confidence", 0.0)),
                "created_at": row.get("created_at", ""),
                "description": str(row.get("description", ""))[:96],
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    ids = [str(row.get("id", "")) for row in records if isinstance(row, dict)]
    selected_id = st.selectbox("Inspect record", ids)
    selected = next(
        (r for r in records if isinstance(r, dict) and str(r.get("id", "")) == selected_id),
        None,
    )

    if isinstance(selected, dict):
        st.json(selected)
        if st.button("Delete selected record"):
            try:
                client.delete_history_record(selected_id)
                _refresh_history(client)
                st.success("Record deleted.")
            except Exception as exc:
                st.error(f"Delete failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Review Queue tab
# ═══════════════════════════════════════════════════════════════════════════
def _refresh_queue(client: StreamlitAPIClient) -> None:
    st.session_state.queue_rows = client.fetch_operator_queue()


def _render_queue_tab(client: StreamlitAPIClient) -> None:
    st.markdown(
        '<div class="section-title">Operator Queue</div>',
        unsafe_allow_html=True,
    )

    if st.button("Refresh queue"):
        try:
            _refresh_queue(client)
        except Exception as exc:
            st.error(f"Queue refresh failed: {exc}")

    if not st.session_state.queue_rows:
        try:
            _refresh_queue(client)
        except Exception as exc:
            st.error(f"Queue load failed: {exc}")
            return

    queue_rows = st.session_state.queue_rows
    if not queue_rows:
        st.info("No records currently require operator review.")
        return

    for row in queue_rows:
        if not isinstance(row, dict):
            continue
        result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
        record_id = str(row.get("id", ""))
        category = str(result.get("category", "unknown"))
        confidence = _as_pct(result.get("confidence", 0.0))
        description = str(row.get("description", ""))

        with st.container(border=True):
            col_a, col_b, col_c = st.columns([1.2, 1, 4])
            with col_a:
                st.markdown(
                    f"**Category**<br>{category_badge_html(category)}",
                    unsafe_allow_html=True,
                )
            col_b.metric("Confidence", confidence)
            with col_c:
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#d4d4d4">{description[:120]}</div>',
                    unsafe_allow_html=True,
                )

            with st.form(f"queue_review_{record_id}", clear_on_submit=True):
                action = st.selectbox(
                    "Action",
                    ["approve", "reject", "override"],
                    key=f"queue_action_{record_id}",
                )
                override = None
                if action == "override":
                    override = st.selectbox(
                        "Override category",
                        CATEGORY_OPTIONS,
                        key=f"queue_override_{record_id}",
                    )
                comment = st.text_input("Comment", key=f"queue_comment_{record_id}")
                submit = st.form_submit_button("Submit", use_container_width=True)

            if submit:
                try:
                    client.submit_operator_review(
                        record_id=record_id,
                        action=action,
                        override_category=override,
                        comment=comment or None,
                    )
                    _refresh_queue(client)
                    st.success(f"Reviewed {record_id}.")
                except Exception as exc:
                    st.error(f"Review failed for {record_id}: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main() -> None:
    _ensure_state()
    client = _client()

    # Inject styles
    st.markdown(get_stylesheet(), unsafe_allow_html=True)

    # Header
    st.markdown(header_html(), unsafe_allow_html=True)

    # Connection settings (collapsible)
    with st.expander("Connection", expanded=False):
        st.session_state.api_base_url = st.text_input(
            "Classifier API base URL",
            value=st.session_state.api_base_url,
            help="FastAPI backend that serves /api/* endpoints.",
        ).rstrip("/")

    # Tabs
    workspace_tab, queue_tab, history_tab = st.tabs(
        ["Workspace", "Review Queue", "History"]
    )

    # ── Workspace ──────────────────────────────────────────────────────
    with workspace_tab:
        main_col, side_col = st.columns([3, 2], gap="large")

        with main_col:
            _render_input_panel(client)

            # Re-read snapshot after input panel (classification may have updated it)
            snapshot = st.session_state.snapshot
            has_data = snapshot.status in ("complete", "error") or snapshot.events

            # Show detail header + full workflow only when we have actual data
            if has_data:
                st.divider()
                # Detail header — native Streamlit to avoid HTML sanitizer issues
                _dh_cols = st.columns([3, 1, 1])
                _dh_cols[0].markdown(f"**{st.session_state.description_input[:80]}**")
                if isinstance(snapshot.result, dict):
                    _dh_cols[1].markdown(
                        category_badge_html(str(snapshot.result.get("category", "other"))),
                        unsafe_allow_html=True,
                    )
                    _dh_cols[2].metric(
                        "Confidence",
                        _as_pct(snapshot.result.get("confidence", 0)),
                    )
                if snapshot.elapsed_seconds > 0:
                    st.caption(f"Completed in {snapshot.elapsed_seconds:.1f}s")
                _render_workflow(snapshot)
                _render_reasoning(snapshot)
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                _render_result(snapshot)
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                _render_operator_actions(client, snapshot)

                # Reset button
                if snapshot.status == "complete":
                    st.markdown("")  # spacer
                    if st.button("Classify Another", use_container_width=True):
                        st.session_state.snapshot = _empty_snapshot()
                        st.session_state._pending_description = ""
                        st.rerun()

        with side_col:
            _render_sidebar(snapshot)

    # ── Review Queue ───────────────────────────────────────────────────
    with queue_tab:
        _render_queue_tab(client)

    # ── History ────────────────────────────────────────────────────────
    with history_tab:
        _render_history_tab(client)


if __name__ == "__main__":
    main()
