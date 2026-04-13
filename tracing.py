"""Langfuse tracing and structured event logging."""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Try to initialize Langfuse; fall back to local-only logging if not configured.
_langfuse = None
try:
    from langfuse import Langfuse

    if os.getenv("LANGFUSE_SECRET_KEY"):
        _langfuse = Langfuse(
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
except Exception:
    pass


class RunTracer:
    """Trace a single supply chain run to Langfuse and/or local JSON."""

    def __init__(self, run_id: str, config: dict):
        self.run_id = run_id
        self.config = config
        self.events: list[dict] = []
        self._trace = None
        self._langfuse_api = None

        if not _langfuse:
            return

        try:
            if hasattr(_langfuse, "trace"):
                self._langfuse_api = "legacy"
                self._trace = _langfuse.trace(
                    id=run_id,
                    name="supply_chain_run",
                    metadata=config,
                )
            elif hasattr(_langfuse, "start_observation"):
                self._langfuse_api = "v4"
                self._trace = _langfuse.start_observation(
                    name="supply_chain_run",
                    as_type="chain",
                    input={"run_id": run_id, "config": config},
                    metadata={"run_id": run_id, "config": config},
                )
        except Exception:
            self._trace = None
            self._langfuse_api = None

    def _create_langfuse_event(self, name: str, payload: dict):
        """Emit an event without letting tracing failures break the run."""
        if not self._trace:
            return

        try:
            if self._langfuse_api == "legacy":
                self._trace.event(name=name, metadata=payload)
            elif self._langfuse_api == "v4":
                self._trace.create_event(name=name, metadata=payload)
        except Exception:
            pass

    def log_turn(self, turn_data: dict, negotiation_id: str):
        """Log a structured event for one agent turn."""
        event = {
            "event_type": "agent_turn",
            "timestamp": turn_data.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "run_id": self.run_id,
            "negotiation": negotiation_id,
            "round": turn_data["round"],
            "agent_role": turn_data["agent_role"],
            "agent_model": self.config.get("model", "unknown"),
            "action": turn_data["action"],
            "offer_price": turn_data.get("offer_price"),
            "market_price_seen": turn_data.get("market_price_seen"),
            "ground_truth_price": turn_data.get("ground_truth_price"),
            "price_divergence": turn_data.get("price_divergence"),
            "reservation_price": turn_data.get("reservation_price"),
            "message": turn_data.get("message"),
            "current_state": turn_data.get("current_state"),
            "expected_outcome": turn_data.get("expected_outcome"),
            "approach": turn_data.get("approach"),
            "intended_action": turn_data.get("intended_action"),
            "tokens": {
                "input": turn_data.get("input_tokens", 0),
                "output": turn_data.get("output_tokens", 0),
            },
            "latency_ms": turn_data.get("latency_ms", 0),
        }
        self.events.append(event)

        self._create_langfuse_event(
            name=f"{negotiation_id}.{turn_data['agent_role']}.{turn_data['action']}",
            payload=event,
        )

    def log_negotiation_result(self, result: dict):
        """Log a negotiation-level summary event."""
        event = {
            "event_type": "negotiation_complete",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "run_id": self.run_id,
            "negotiation": result["negotiation_id"],
            "outcome": result["outcome"],
            "final_price": result.get("final_price"),
            "rounds": result["rounds"],
            "failure_reason": result.get("failure_reason"),
            "seller_reservation": result.get("seller_reservation"),
            "buyer_reservation": result.get("buyer_reservation"),
            "seller_surplus": result.get("seller_surplus"),
            "buyer_surplus": result.get("buyer_surplus"),
        }
        self.events.append(event)

        self._create_langfuse_event(
            name=f"{result['negotiation_id']}.complete",
            payload=event,
        )

    def log_generation(
        self,
        negotiation_id: str,
        agent_role: str,
        round_num: int,
        input_messages: list,
        output_content: list,
        model: str,
        usage: dict,
        latency_ms: int,
    ):
        """Log an LLM generation to Langfuse."""
        if not self._trace:
            return

        try:
            if self._langfuse_api == "legacy":
                self._trace.generation(
                    name=f"{negotiation_id}.{agent_role}.round{round_num}",
                    model=model,
                    input=input_messages,
                    output=output_content,
                    usage=usage,
                    metadata={"latency_ms": latency_ms},
                )
            elif self._langfuse_api == "v4":
                generation = self._trace.start_observation(
                    name=f"{negotiation_id}.{agent_role}.round{round_num}",
                    as_type="generation",
                    model=model,
                    input=input_messages,
                    output=output_content,
                    usage_details=usage,
                    metadata={"latency_ms": latency_ms},
                )
                generation.end()
        except Exception:
            pass

    def finalize(self, final_state: dict) -> dict:
        """Finalize the trace and return the complete run record."""
        run_record = {
            "run_id": self.run_id,
            "timestamp": final_state.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "config": self.config,
            "overall_outcome": final_state["overall_outcome"],
            "supplier_manufacturer": final_state.get("supplier_mfr_result"),
            "manufacturer_retailer": final_state.get("mfr_retailer_result"),
            "events": self.events,
        }

        if self._trace:
            try:
                self._trace.update(output={"outcome": final_state["overall_outcome"]})
                if hasattr(self._trace, "end"):
                    self._trace.end()
                _langfuse.flush()
            except Exception:
                pass

        return run_record


def save_run(run_record: dict, output_dir: str = "runs") -> str:
    """Save a run record as JSON."""
    Path(output_dir).mkdir(exist_ok=True)
    outcome = run_record["overall_outcome"]
    run_id = run_record["run_id"][:8]
    filename = f"run_{run_id}_{outcome}.json"
    filepath = Path(output_dir) / filename

    with open(filepath, "w") as f:
        json.dump(run_record, f, indent=2, default=str)

    return str(filepath)
