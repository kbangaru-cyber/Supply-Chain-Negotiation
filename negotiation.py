"""Bilateral negotiation engine between two agents using Claude API."""

import json
import time
from dataclasses import dataclass, field
from anthropic import Anthropic
from agents import AgentDefinition
from tools import NEGOTIATION_TOOLS, execute_check_market_price
from config import SimulationConfig


@dataclass
class TurnRecord:
    round: int
    agent_role: str
    action: str
    offer_price: float | None = None
    message: str | None = None
    current_state: str | None = None
    expected_outcome: str | None = None
    approach: str | None = None
    intended_action: str | None = None
    market_price_seen: float | None = None
    ground_truth_price: float | None = None
    price_divergence: float | None = None
    reservation_price: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    timestamp: str = ""


@dataclass
class NegotiationResult:
    negotiation_id: str  # e.g. "supplier_manufacturer"
    outcome: str  # "success" or "failure"
    final_price: float | None = None
    rounds: int = 0
    failure_reason: str | None = None  # "walk_away" or "round_limit"
    turns: list[TurnRecord] = field(default_factory=list)
    seller_reservation: float = 0.0
    buyer_reservation: float = 0.0

    @property
    def seller_surplus(self) -> float | None:
        if self.final_price is not None:
            return round(self.final_price - self.seller_reservation, 2)
        return None

    @property
    def buyer_surplus(self) -> float | None:
        if self.final_price is not None:
            return round(self.buyer_reservation - self.final_price, 2)
        return None


ACTION_TOOLS = {"make_offer", "accept_offer", "reject_offer", "walk_away"}


def run_negotiation(
    client: Anthropic,
    seller: AgentDefinition,
    buyer: AgentDefinition,
    negotiation_id: str,
    config: SimulationConfig,
) -> NegotiationResult:
    """Run a bilateral negotiation between seller and buyer."""
    result = NegotiationResult(
        negotiation_id=negotiation_id,
        outcome="failure",
        seller_reservation=seller.config.reservation_price,
        buyer_reservation=buyer.config.reservation_price,
    )

    # Each agent has their own conversation history
    seller_messages: list[dict] = [
        {"role": "user", "content": "The negotiation is starting. You are the SELLER. Make your opening move."}
    ]
    buyer_messages: list[dict] = []

    current_agent = seller  # seller goes first
    current_messages = seller_messages
    last_offer_price: float | None = None
    round_num = 0

    while round_num < config.max_rounds:
        round_num += 1
        result.rounds = round_num

        # Run the agent's turn (may include check_market_price + action)
        turn = _run_agent_turn(
            client=client,
            agent=current_agent,
            messages=current_messages,
            config=config,
            round_num=round_num,
            negotiation_id=negotiation_id,
        )
        result.turns.append(turn)

        # Process the action
        if turn.action == "accept_offer":
            if last_offer_price is not None:
                result.outcome = "success"
                result.final_price = last_offer_price
            else:
                # Can't accept with no offer on the table
                result.outcome = "failure"
                result.failure_reason = "invalid_accept"
            return result

        elif turn.action == "walk_away":
            result.outcome = "failure"
            result.failure_reason = "walk_away"
            return result

        elif turn.action == "make_offer":
            last_offer_price = turn.offer_price
            # Deliver the offer to the other agent on their next turn
            other_agent = buyer if current_agent is seller else seller
            other_messages = buyer_messages if current_agent is seller else seller_messages

            if not other_messages:
                # First message for this agent
                other_messages.append({
                    "role": "user",
                    "content": (
                        f"The negotiation is starting. You are the BUYER. "
                        f"The seller has opened with an offer of ${turn.offer_price:.2f}. "
                        f'Their message: "{turn.message}"\n'
                        f"It is your turn to respond."
                    ),
                })
            else:
                other_messages.append({
                    "role": "user",
                    "content": (
                        f"The other party has {'counter-' if round_num > 1 else ''}offered ${turn.offer_price:.2f}. "
                        f'Their message: "{turn.message}"\n'
                        f"It is your turn to respond."
                    ),
                })

            # Switch to the other agent
            current_agent = other_agent
            current_messages = other_messages

        elif turn.action == "reject_offer":
            # Deliver rejection to the other agent
            other_agent = buyer if current_agent is seller else seller
            other_messages = buyer_messages if current_agent is seller else seller_messages

            other_messages.append({
                "role": "user",
                "content": (
                    f'The other party rejected your offer. Their reason: "{turn.message}"\n'
                    f"It is your turn to make a new offer or take another action."
                ),
            })

            current_agent = other_agent
            current_messages = other_messages

    # Hit round limit
    result.outcome = "failure"
    result.failure_reason = "round_limit"
    return result


def _run_agent_turn(
    client: Anthropic,
    agent: AgentDefinition,
    messages: list[dict],
    config: SimulationConfig,
    round_num: int,
    negotiation_id: str,
) -> TurnRecord:
    """Execute one agent turn. Agent may call check_market_price then must take an action."""
    turn = TurnRecord(
        round=round_num,
        agent_role=agent.role,
        action="unknown",
        reservation_price=agent.config.reservation_price,
        ground_truth_price=config.product.ground_truth_price,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    working_messages = list(messages)
    total_input_tokens = 0
    total_output_tokens = 0

    # Loop to handle tool calls (agent might check price then act)
    for _ in range(3):  # max 3 API calls per turn (price check + action + safety)
        start = time.time()
        response = client.messages.create(
            model=config.model,
            max_tokens=1024,
            system=agent.system_prompt,
            tools=NEGOTIATION_TOOLS,
            messages=working_messages,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        turn.latency_ms += elapsed_ms
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Parse response content blocks
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if not tool_uses:
            # Agent responded with text only (shouldn't happen, but handle it)
            # Append assistant response and prompt for action
            working_messages.append({"role": "assistant", "content": response.content})
            working_messages.append({
                "role": "user",
                "content": "You must use one of the available tools to take an action. Please call make_offer, accept_offer, reject_offer, or walk_away.",
            })
            continue

        # Process first tool use
        tool_call = tool_uses[0]
        tool_name = tool_call.name
        tool_input = tool_call.input

        if tool_name == "check_market_price":
            # Execute the market price tool
            price_result = execute_check_market_price(
                product=tool_input.get("product", config.product.name),
                config=config,
            )
            turn.market_price_seen = price_result["market_price"]
            turn.price_divergence = price_result["_noise"]
            agent.market_prices_seen.append(price_result["market_price"])

            # Feed result back and let agent continue
            working_messages.append({"role": "assistant", "content": response.content})
            working_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps({
                            "product": price_result["product"],
                            "market_price": price_result["market_price"],
                        }),
                    }
                ],
            })
            continue

        # It's an action tool
        if tool_name in ACTION_TOOLS:
            turn.action = tool_name
            turn.current_state = tool_input.get("current_state")
            turn.expected_outcome = tool_input.get("expected_outcome")
            turn.approach = tool_input.get("approach")
            turn.intended_action = tool_input.get("intended_action")
            if tool_name == "make_offer":
                turn.offer_price = tool_input.get("price")
                turn.message = tool_input.get("message", "")
            elif tool_name == "accept_offer":
                turn.message = tool_input.get("message", "")
            elif tool_name == "reject_offer":
                turn.message = tool_input.get("reason", "")
            elif tool_name == "walk_away":
                turn.message = tool_input.get("reason", "")

            # Append assistant response to this agent's history for continuity
            working_messages.append({"role": "assistant", "content": response.content})
            # Add a synthetic tool result so the conversation is well-formed
            working_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps({"status": "ok"}),
                    }
                ],
            })
            break

    # Update the original messages list in-place
    messages.clear()
    messages.extend(working_messages)

    turn.input_tokens = total_input_tokens
    turn.output_tokens = total_output_tokens
    return turn
