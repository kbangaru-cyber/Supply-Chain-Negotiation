"""Full supply chain simulation orchestrator using LangGraph."""

import uuid
import time
from typing import TypedDict, Literal
from dataclasses import asdict
from anthropic import Anthropic
from langgraph.graph import StateGraph, END

from config import SimulationConfig
from agents import (
    build_supplier,
    build_manufacturer_as_buyer,
    build_manufacturer_as_seller,
    build_retailer,
)
from negotiation import run_negotiation, NegotiationResult
from tracing import RunTracer, save_run


class SupplyChainState(TypedDict):
    run_id: str
    phase: str
    config: dict
    supplier_mfr_result: dict | None
    mfr_retailer_result: dict | None
    overall_outcome: str
    timestamp: str
    tracer: RunTracer | None


def _result_to_dict(result: NegotiationResult) -> dict:
    d = asdict(result)
    d["seller_surplus"] = result.seller_surplus
    d["buyer_surplus"] = result.buyer_surplus
    return d


def build_supply_chain_graph(client: Anthropic, config: SimulationConfig) -> StateGraph:
    """Build the LangGraph state machine for the two-phase supply chain."""

    def negotiate_supply(state: SupplyChainState) -> dict:
        """Phase 1: Supplier <-> Manufacturer negotiation."""
        supplier = build_supplier(config.supplier, config.product.name)
        mfr_buyer = build_manufacturer_as_buyer(config.manufacturer, config.product.name)

        result = run_negotiation(
            client=client,
            seller=supplier,
            buyer=mfr_buyer,
            negotiation_id="supplier_manufacturer",
            config=config,
        )
        result_dict = _result_to_dict(result)
        tracer = state.get("tracer")
        if tracer:
            for turn in result.turns:
                tracer.log_turn(asdict(turn), "supplier_manufacturer")
            tracer.log_negotiation_result(result_dict)
        return {
            "supplier_mfr_result": result_dict,
            "phase": "supply_done",
        }

    def negotiate_retail(state: SupplyChainState) -> dict:
        """Phase 2: Manufacturer <-> Retailer negotiation."""
        supply_result = state["supplier_mfr_result"]
        buy_price = supply_result["final_price"]

        mfr_seller = build_manufacturer_as_seller(
            config.manufacturer,
            config.product.name,
            buy_price=buy_price,
            margin=config.manufacturer.margin,
        )
        retailer = build_retailer(config.retailer, config.product.name)

        result = run_negotiation(
            client=client,
            seller=mfr_seller,
            buyer=retailer,
            negotiation_id="manufacturer_retailer",
            config=config,
        )
        result_dict = _result_to_dict(result)
        tracer = state.get("tracer")
        if tracer:
            for turn in result.turns:
                tracer.log_turn(asdict(turn), "manufacturer_retailer")
            tracer.log_negotiation_result(result_dict)
        return {
            "mfr_retailer_result": result_dict,
            "phase": "retail_done",
        }

    def evaluate_run(state: SupplyChainState) -> dict:
        """Determine overall outcome."""
        supply = state["supplier_mfr_result"]
        retail = state.get("mfr_retailer_result")

        if supply["outcome"] != "success":
            outcome = "failure_at_supply"
        elif retail is None or retail["outcome"] != "success":
            outcome = "failure_at_retail"
        else:
            outcome = "success"

        return {"overall_outcome": outcome, "phase": "complete"}

    def route_after_supply(state: SupplyChainState) -> Literal["negotiate_retail", "evaluate_run"]:
        if state["supplier_mfr_result"]["outcome"] == "success":
            return "negotiate_retail"
        return "evaluate_run"

    # Build the graph
    graph = StateGraph(SupplyChainState)
    graph.add_node("negotiate_supply", negotiate_supply)
    graph.add_node("negotiate_retail", negotiate_retail)
    graph.add_node("evaluate_run", evaluate_run)

    graph.set_entry_point("negotiate_supply")
    graph.add_conditional_edges("negotiate_supply", route_after_supply)
    graph.add_edge("negotiate_retail", "evaluate_run")
    graph.add_edge("evaluate_run", END)

    return graph.compile()


def run_supply_chain(client: Anthropic, config: SimulationConfig) -> dict:
    """Execute one full supply chain simulation run. Returns the saved run record."""
    run_id = str(uuid.uuid4())
    config_dict = {
        "product": config.product.name,
        "ground_truth_price": config.product.ground_truth_price,
        "sigma": config.sigma,
        "max_rounds": config.max_rounds,
        "model": config.model,
        "supplier_reservation": config.supplier.reservation_price,
        "manufacturer_reservation": config.manufacturer.reservation_price,
        "manufacturer_margin": config.manufacturer.margin,
        "retailer_reservation": config.retailer.reservation_price,
    }

    tracer = RunTracer(run_id, config_dict)
    graph = build_supply_chain_graph(client, config)

    initial_state: SupplyChainState = {
        "run_id": run_id,
        "phase": "start",
        "config": config_dict,
        "supplier_mfr_result": None,
        "mfr_retailer_result": None,
        "overall_outcome": "pending",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tracer": tracer,
    }

    final_state = graph.invoke(initial_state)

    # Finalize trace and save
    run_record = tracer.finalize(final_state)
    filepath = save_run(run_record)
    print(f"  Run saved to {filepath}")

    return run_record
