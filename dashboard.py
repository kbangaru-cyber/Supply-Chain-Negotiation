"""Streamlit dashboard for supply chain negotiation runs."""

import json
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Supply Chain Negotiation Dashboard", layout="wide")


NEGOTIATION_LABELS = {
    "supplier_manufacturer": "Supplier <-> Manufacturer",
    "manufacturer_retailer": "Manufacturer <-> Retailer",
}

ROLE_THEMES = {
    "supplier": {
        "label": "Supplier",
        "subtitle": "seller",
        "class_name": "supplier",
    },
    "manufacturer_buyer": {
        "label": "Manufacturer",
        "subtitle": "buyer",
        "class_name": "manufacturer",
    },
    "manufacturer_seller": {
        "label": "Manufacturer",
        "subtitle": "seller",
        "class_name": "manufacturer",
    },
    "retailer": {
        "label": "Retailer",
        "subtitle": "buyer",
        "class_name": "retailer",
    },
}

st.markdown(
    """
<style>
    .chat-note {
        color: #5f6b7a;
        font-size: 0.95rem;
        margin-bottom: 1rem;
    }
    .transcript-row {
        margin: 0.4rem 0 1.2rem 0;
    }
    .state-card, .action-card {
        border-radius: 18px;
        padding: 1rem 1.1rem;
        border: 1px solid #d7dde5;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
    }
    .state-card {
        margin: 0.45rem 0 0.45rem 0;
    }
    .action-card {
        margin: 0.4rem 0 0 2rem;
        background: #131923;
        border-color: #293242;
        color: #eff4fb;
    }
    .state-card.supplier {
        background: #fbe9e7;
        border-color: #e7b4ad;
    }
    .state-card.manufacturer {
        background: #eaf3ff;
        border-color: #b6cdee;
    }
    .state-card.retailer {
        background: #edf8ee;
        border-color: #b9dbbc;
    }
    .card-header {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-wrap: wrap;
        margin-bottom: 0.8rem;
    }
    .role-chip {
        border-radius: 999px;
        padding: 0.25rem 0.7rem;
        font-size: 0.84rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #203042;
        background: rgba(255, 255, 255, 0.65);
    }
    .round-chip, .action-chip {
        border-radius: 999px;
        padding: 0.22rem 0.65rem;
        font-size: 0.8rem;
        color: #455468;
        background: rgba(255, 255, 255, 0.55);
    }
    .action-card .round-chip, .action-card .action-chip {
        color: #d6deeb;
        background: rgba(255, 255, 255, 0.08);
    }
    .meta-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.65rem;
        margin-bottom: 0.8rem;
    }
    .meta-box {
        background: rgba(255, 255, 255, 0.7);
        border-radius: 14px;
        padding: 0.7rem 0.8rem;
    }
    .action-card .meta-box {
        background: rgba(255, 255, 255, 0.06);
    }
    .meta-label {
        display: block;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 0.2rem;
    }
    .action-card .meta-label {
        color: #8ea0b8;
    }
    .meta-value {
        display: block;
        font-size: 1rem;
        font-weight: 700;
        color: #17202f;
    }
    .action-card .meta-value {
        color: #eff4fb;
    }
    .chat-text {
        color: #1f2937;
        line-height: 1.55;
        white-space: pre-wrap;
    }
    .action-card .chat-text {
        color: #eef3fa;
    }
    .chat-footer {
        margin-top: 0.75rem;
        color: #526273;
        font-size: 0.88rem;
    }
    .action-card .chat-footer {
        color: #9ba9bb;
    }
    .state-title, .action-title {
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }
    .state-title {
        color: #1e293b;
    }
    .action-title {
        color: #ffffff;
    }
    .rationale-list {
        display: grid;
        gap: 0.55rem;
        margin-top: 0.2rem;
    }
    .rationale-item {
        background: rgba(255, 255, 255, 0.44);
        border-radius: 14px;
        padding: 0.75rem 0.9rem;
    }
    .rationale-question {
        display: block;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #526273;
        margin-bottom: 0.25rem;
    }
    .rationale-answer {
        color: #1f2937;
        line-height: 1.45;
        white-space: pre-wrap;
    }
    .transcript-divider {
        height: 1px;
        margin: 0.4rem 0 0 2rem;
        background: linear-gradient(90deg, rgba(148, 163, 184, 0.35), rgba(148, 163, 184, 0));
    }
</style>
""",
    unsafe_allow_html=True,
)


def get_turns(negotiation_data):
    """Extract turn records from a negotiation result."""
    if negotiation_data is None:
        return []
    return negotiation_data.get("turns", [])


def format_currency(value, fallback="N/A"):
    """Format numeric values as USD."""
    if value is None:
        return fallback
    return f"${value:.2f}"


def get_negotiation_label(negotiation_id):
    """Return a human-readable negotiation label."""
    return NEGOTIATION_LABELS.get(negotiation_id, negotiation_id.replace("_", " ").title())


def get_role_theme(role):
    """Return display settings for a role."""
    return ROLE_THEMES.get(
        role,
        {
            "label": role.replace("_", " ").title(),
            "subtitle": "",
            "class_name": "manufacturer",
        },
    )


def get_constraint_label(role):
    """Return the economic constraint label for a role."""
    if role in {"supplier", "manufacturer_seller"}:
        return "Min Sell"
    return "Max Buy"


def get_rationale_value(turn, primary_key, fallback_text, legacy_key=None):
    """Read structured rationale fields with a fallback for older runs."""
    value = turn.get(primary_key)
    if value:
        return value

    if legacy_key:
        legacy_value = turn.get(legacy_key)
        if legacy_value:
            return legacy_value

    return fallback_text


def get_market_footer(turn):
    """Return market signal text for a turn when available."""
    market_price = turn.get("market_price_seen")
    if market_price is None:
        return ""

    divergence = turn.get("price_divergence")
    if divergence is None:
        return f"Market view: {format_currency(market_price)}"
    return (
        f"Market view: {format_currency(market_price)} "
        f"({divergence:+.2f} vs ground truth)"
    )


def get_action_title(turn, prior_offer):
    """Return the title for the action card."""
    action = turn["action"]
    if action == "make_offer" and turn.get("offer_price") is not None:
        return f"Make Offer: {format_currency(turn['offer_price'])}"
    if action == "accept_offer":
        if prior_offer is not None:
            return f"Accept Offer: {format_currency(prior_offer)}"
        return "Accept Offer"
    if action == "reject_offer":
        return "Reject Offer"
    if action == "walk_away":
        return "Walk Away"
    return action.replace("_", " ").title()


def get_action_price_metric(turn, prior_offer):
    """Return the single action-price box for the action card when applicable."""
    action = turn["action"]
    if action == "make_offer" and turn.get("offer_price") is not None:
        return ("Offer Price", format_currency(turn["offer_price"]))
    if action == "accept_offer" and prior_offer is not None:
        return ("Accepted Price", format_currency(prior_offer))
    return (None, None)


def render_chat_turn(turn, prior_offer):
    """Render one negotiation turn as an internal-state card plus action card."""
    theme = get_role_theme(turn["agent_role"])
    role_label = theme["label"]
    subtitle = theme["subtitle"]
    role_text = role_label if not subtitle else f"{role_label} ({subtitle})"
    constraint_label = get_constraint_label(turn["agent_role"])
    message = escape(turn.get("message") or "No free-text rationale recorded for this turn.")
    current_state = escape(
        get_rationale_value(
            turn,
            "current_state",
            "No structured current-state summary recorded for this turn.",
        )
    )
    expected_outcome = escape(
        get_rationale_value(
            turn,
            "expected_outcome",
            "No structured expectation recorded for this turn.",
            legacy_key="prediction",
        )
    )
    approach = escape(
        get_rationale_value(
            turn,
            "approach",
            "No structured approach summary recorded for this turn.",
            legacy_key="reasoning_summary",
        )
    )
    intended_action = escape(
        get_rationale_value(
            turn,
            "intended_action",
            "No structured intended-action summary recorded for this turn.",
        )
    )
    footer = get_market_footer(turn)
    market_text = footer if footer else "Market view: no market check this turn"

    state_html = f"""
<div class="transcript-row">
    <div class="state-card {theme['class_name']}">
        <div class="card-header">
            <span class="role-chip">{escape(role_text)}</span>
            <span class="round-chip">Round {turn['round']}</span>
            <span class="action-chip">Internal State</span>
        </div>
        <div class="state-title">{escape(role_label)} Agent Internal State</div>
        <div class="meta-grid">
            <div class="meta-box">
                <span class="meta-label">{escape(constraint_label)}</span>
                <span class="meta-value">{escape(format_currency(turn.get('reservation_price')))}</span>
            </div>
            <div class="meta-box">
                <span class="meta-label">Market Price Seen</span>
                <span class="meta-value">{escape(format_currency(turn.get('market_price_seen'), 'No check'))}</span>
            </div>
        </div>
        <div class="rationale-list">
            <div class="rationale-item">
                <span class="rationale-question">What is my current state?</span>
                <div class="rationale-answer">{current_state}</div>
            </div>
            <div class="rationale-item">
                <span class="rationale-question">What might happen?</span>
                <div class="rationale-answer">{expected_outcome}</div>
            </div>
            <div class="rationale-item">
                <span class="rationale-question">How am I going to approach it?</span>
                <div class="rationale-answer">{approach}</div>
            </div>
            <div class="rationale-item">
                <span class="rationale-question">What am I going to do?</span>
                <div class="rationale-answer">{intended_action}</div>
            </div>
        </div>
        <div class="chat-footer">{escape(market_text)}</div>
    </div>
    <div class="action-card">
        <div class="card-header">
            <span class="role-chip">{escape(role_text)}</span>
            <span class="round-chip">Round {turn['round']}</span>
            <span class="action-chip">{escape(turn['action'].replace('_', ' ').title())}</span>
        </div>
        <div class="action-title">{escape(get_action_title(turn, prior_offer))}</div>
        <div class="chat-text">{message}</div>
    </div>
    <div class="transcript-divider"></div>
</div>
"""
    st.markdown(state_html, unsafe_allow_html=True)


def update_offer_state(turn, prior_offer):
    """Update the current offer on the table after a turn."""
    action = turn["action"]
    if action == "make_offer" and turn.get("offer_price") is not None:
        return turn["offer_price"]
    if action in {"reject_offer", "walk_away"}:
        return None
    return prior_offer


# --- Sidebar: Run selector ---
st.sidebar.title("Run Selector")

runs_dir = Path("runs")
if not runs_dir.exists() or not list(runs_dir.glob("*.json")):
    st.warning("No runs found. Run `python run.py` first to generate simulation data.")
    st.stop()

run_files = sorted(runs_dir.glob("*.json"), reverse=True)
run_labels = [f.stem for f in run_files]
selected_label = st.sidebar.selectbox("Select a run", run_labels)
selected_file = runs_dir / f"{selected_label}.json"

with open(selected_file) as f:
    run = json.load(f)

events = run.get("events", [])
turn_events = [event for event in events if event["event_type"] == "agent_turn"]

# Quick stats in sidebar
outcome = run["overall_outcome"]
outcome_color = "green" if outcome == "success" else "red"
st.sidebar.markdown(f"**Outcome:** :{outcome_color}[{outcome}]")
st.sidebar.markdown(f"**Product:** {run['config']['product']}")
st.sidebar.markdown(f"**Ground truth price:** {format_currency(run['config']['ground_truth_price'])}")
st.sidebar.markdown(f"**Noise (sigma):** {run['config']['sigma']}")
st.sidebar.markdown(f"**Model:** {run['config']['model']}")

st.sidebar.markdown("---")
st.sidebar.markdown("**Reservation Prices**")
st.sidebar.markdown(f"Supplier min sell: {format_currency(run['config']['supplier_reservation'])}")
st.sidebar.markdown(
    f"Manufacturer max buy: {format_currency(run['config']['manufacturer_reservation'])}"
)
st.sidebar.markdown(f"Manufacturer margin: {format_currency(run['config']['manufacturer_margin'])}")
st.sidebar.markdown(f"Retailer max buy: {format_currency(run['config']['retailer_reservation'])}")


# --- Tab layout ---
tab1, tab2, tab3 = st.tabs([
    "Negotiation",
    "Analysis",
    "Results",
])


# ============================================================
# TAB 1: Negotiation
# ============================================================
with tab1:
    st.header("Negotiation")
    st.markdown(
        """
<div class="chat-note">
Each transcript shows a structured rationale block answering four questions:
current state, what might happen, how the agent will approach the turn, and what
the agent is about to do. The action card then shows the actual move. Supplier
cards are pale red, manufacturer cards are pale blue, and retailer cards are
pale green.
</div>
""",
        unsafe_allow_html=True,
    )

    for negotiation_id in ["supplier_manufacturer", "manufacturer_retailer"]:
        negotiation_label = get_negotiation_label(negotiation_id)
        negotiation_data = run.get(negotiation_id)

        if negotiation_data is None:
            st.subheader(f"{negotiation_label} - Skipped")
            st.info("This negotiation did not occur because the prior stage failed.")
            continue

        st.subheader(negotiation_label)
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("Outcome", negotiation_data["outcome"].upper())
        with summary_cols[1]:
            st.metric("Final Price", format_currency(negotiation_data.get("final_price")))
        with summary_cols[2]:
            st.metric("Seller Floor", format_currency(negotiation_data["seller_reservation"]))
        with summary_cols[3]:
            st.metric("Buyer Ceiling", format_currency(negotiation_data["buyer_reservation"]))

        turns = get_turns(negotiation_data)
        if not turns:
            st.info("No turn data available for this negotiation.")
            continue

        prior_offer = None
        for turn in turns:
            render_chat_turn(turn, prior_offer)
            prior_offer = update_offer_state(turn, prior_offer)


# ============================================================
# TAB 2: Analysis
# ============================================================
with tab2:
    st.header("Analysis")

    st.subheader("Price Waterfall")
    waterfall_labels = []
    waterfall_values = []
    waterfall_measures = []

    supplier_res = run["config"]["supplier_reservation"]
    waterfall_labels.append("Supplier Min")
    waterfall_values.append(supplier_res)
    waterfall_measures.append("absolute")

    supplier_manufacturer = run.get("supplier_manufacturer")
    if supplier_manufacturer and supplier_manufacturer["outcome"] == "success":
        sm_price = supplier_manufacturer["final_price"]
        waterfall_labels.append("S<->M Agreed")
        waterfall_values.append(sm_price - supplier_res)
        waterfall_measures.append("relative")

        margin = run["config"]["manufacturer_margin"]
        waterfall_labels.append("Mfr Margin")
        waterfall_values.append(margin)
        waterfall_measures.append("relative")

        manufacturer_retailer = run.get("manufacturer_retailer")
        if manufacturer_retailer and manufacturer_retailer["outcome"] == "success":
            mr_price = manufacturer_retailer["final_price"]
            waterfall_labels.append("M<->R Agreed")
            waterfall_values.append(mr_price - sm_price - margin)
            waterfall_measures.append("relative")

            waterfall_labels.append("Retailer Paid")
            waterfall_values.append(mr_price)
            waterfall_measures.append("total")

    if len(waterfall_labels) > 1:
        figure = go.Figure(
            go.Waterfall(
                x=waterfall_labels,
                y=waterfall_values,
                measure=waterfall_measures,
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                textposition="outside",
                text=[format_currency(value) for value in waterfall_values],
            )
        )
        figure.update_layout(
            title="Price Flow Through Supply Chain",
            yaxis_title="Price ($)",
            showlegend=False,
            height=400,
        )
        st.plotly_chart(figure, use_container_width=True)
    else:
        st.info("Not enough data for the waterfall chart because phase 1 did not succeed.")

    st.subheader("Market Price Beliefs vs. Ground Truth")
    for negotiation_id in ["supplier_manufacturer", "manufacturer_retailer"]:
        negotiation_label = get_negotiation_label(negotiation_id)
        negotiation_turns = [
            event
            for event in turn_events
            if event["negotiation"] == negotiation_id and event.get("market_price_seen") is not None
        ]
        if not negotiation_turns:
            continue

        figure = go.Figure()
        ground_truth = run["config"]["ground_truth_price"]

        roles = sorted({turn["agent_role"] for turn in negotiation_turns})
        for role in roles:
            role_turns = [turn for turn in negotiation_turns if turn["agent_role"] == role]
            theme = get_role_theme(role)
            line_color = {
                "supplier": "#d97d73",
                "manufacturer": "#5a8fd8",
                "retailer": "#69a86f",
            }[theme["class_name"]]
            figure.add_trace(
                go.Scatter(
                    x=[turn["round"] for turn in role_turns],
                    y=[turn["market_price_seen"] for turn in role_turns],
                    mode="lines+markers",
                    name=theme["label"] if theme["subtitle"] == "" else f"{theme['label']} ({theme['subtitle']})",
                    line={"color": line_color},
                )
            )

        max_round = max(turn["round"] for turn in negotiation_turns)
        figure.add_trace(
            go.Scatter(
                x=list(range(1, max_round + 1)),
                y=[ground_truth] * max_round,
                mode="lines",
                name="Ground Truth",
                line={"dash": "dash", "color": "gray"},
            )
        )

        figure.update_layout(
            title=f"Belief Divergence - {negotiation_label}",
            xaxis_title="Round",
            yaxis_title="Market Price ($)",
            height=350,
        )
        st.plotly_chart(figure, use_container_width=True)

    st.subheader("Offer Trajectory")
    for negotiation_id in ["supplier_manufacturer", "manufacturer_retailer"]:
        negotiation_label = get_negotiation_label(negotiation_id)
        negotiation_data = run.get(negotiation_id)
        if negotiation_data is None:
            continue

        turns = get_turns(negotiation_data)
        offer_turns = [
            turn for turn in turns if turn["action"] == "make_offer" and turn.get("offer_price") is not None
        ]
        if not offer_turns:
            continue

        figure = go.Figure()
        roles = sorted({turn["agent_role"] for turn in offer_turns})
        for role in roles:
            role_offers = [turn for turn in offer_turns if turn["agent_role"] == role]
            theme = get_role_theme(role)
            line_color = {
                "supplier": "#d97d73",
                "manufacturer": "#5a8fd8",
                "retailer": "#69a86f",
            }[theme["class_name"]]
            figure.add_trace(
                go.Scatter(
                    x=list(range(1, len(role_offers) + 1)),
                    y=[turn["offer_price"] for turn in role_offers],
                    mode="lines+markers",
                    name=theme["label"] if theme["subtitle"] == "" else f"{theme['label']} ({theme['subtitle']})",
                    line={"color": line_color},
                )
            )

        figure.add_hline(
            y=negotiation_data["seller_reservation"],
            line_dash="dash",
            line_color="red",
            annotation_text="Seller min",
        )
        figure.add_hline(
            y=negotiation_data["buyer_reservation"],
            line_dash="dash",
            line_color="green",
            annotation_text="Buyer max",
        )

        figure.update_layout(
            title=f"Offer Trajectory - {negotiation_label}",
            xaxis_title="Offer Number",
            yaxis_title="Price ($)",
            height=350,
        )
        st.plotly_chart(figure, use_container_width=True)


# ============================================================
# TAB 3: Results
# ============================================================
with tab3:
    st.header("Results")

    negotiation_complete_events = [
        event for event in events if event["event_type"] == "negotiation_complete"
    ]

    for negotiation_event in negotiation_complete_events:
        negotiation_id = negotiation_event["negotiation"]
        negotiation_label = get_negotiation_label(negotiation_id)

        st.subheader(negotiation_label)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Outcome", negotiation_event["outcome"].upper())
        with col2:
            st.metric("Rounds", negotiation_event["rounds"])
        with col3:
            st.metric("Final Price", format_currency(negotiation_event.get("final_price")))

        if negotiation_event["outcome"] == "success":
            success_col1, success_col2 = st.columns(2)
            with success_col1:
                st.metric(
                    "Seller Surplus",
                    format_currency(negotiation_event.get("seller_surplus")),
                )
            with success_col2:
                st.metric(
                    "Buyer Surplus",
                    format_currency(negotiation_event.get("buyer_surplus")),
                )
        else:
            st.error(f"Failure reason: {negotiation_event.get('failure_reason', 'unknown')}")

            negotiation_turns = [
                event
                for event in events
                if event["event_type"] == "agent_turn" and event["negotiation"] == negotiation_id
            ]
            if negotiation_turns:
                last_turn = negotiation_turns[-1]
                message_suffix = ""
                if last_turn.get("message"):
                    message_suffix = f' "{last_turn["message"]}"'
                st.warning(
                    f"Breaking point: round {last_turn['round']}, "
                    f"{last_turn['agent_role']} chose {last_turn['action'].replace('_', ' ')}"
                    f"{message_suffix}"
                )

            price_checks = [
                event for event in negotiation_turns if event.get("market_price_seen") is not None
            ]
            divergences = [
                abs(event["price_divergence"])
                for event in price_checks
                if event.get("price_divergence") is not None
            ]
            if divergences:
                average_divergence = sum(divergences) / len(divergences)
                max_divergence = max(divergences)
                recommendation = (
                    "Consider reducing sigma to improve convergence."
                    if average_divergence > 3
                    else "Noise levels appear manageable."
                )
                st.info(
                    f"Price noise analysis: average divergence was "
                    f"{format_currency(average_divergence)}, max was "
                    f"{format_currency(max_divergence)}. Current sigma = "
                    f"{run['config']['sigma']}. {recommendation}"
                )

        negotiation_turns = [
            event
            for event in events
            if event["event_type"] == "agent_turn" and event["negotiation"] == negotiation_id
        ]
        total_input = sum(turn.get("tokens", {}).get("input", 0) for turn in negotiation_turns)
        total_output = sum(turn.get("tokens", {}).get("output", 0) for turn in negotiation_turns)
        total_latency = sum(turn.get("latency_ms", 0) for turn in negotiation_turns)

        st.caption(
            f"Tokens: {total_input:,} input + {total_output:,} output | "
            f"Total latency: {total_latency:,}ms"
        )
        st.divider()

    st.subheader("Overall Assessment")
    if run["overall_outcome"] == "success":
        upstream_price = run["supplier_manufacturer"]["final_price"]
        downstream_price = run["manufacturer_retailer"]["final_price"]
        chain_markup = downstream_price - run["config"]["supplier_reservation"]
        st.success(
            f"The full supply chain closed successfully. "
            f"Upstream price: {format_currency(upstream_price)}. "
            f"Downstream price: {format_currency(downstream_price)}. "
            f"Chain markup from supplier floor: {format_currency(chain_markup)}."
        )
    else:
        st.error(
            f"The supply chain failed at stage: {run['overall_outcome']}. "
            f"Review the Analysis tab for belief divergence and offer trajectory."
        )

    with st.expander("Raw Event Log (JSON)"):
        st.json(events)
