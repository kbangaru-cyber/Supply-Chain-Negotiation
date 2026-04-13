"""Tool definitions and implementations for supply chain agents."""

import random

from config import SimulationConfig


RATIONALE_PROPERTIES = {
    "current_state": {
        "type": "string",
        "description": (
            "A short description of your current situation in the negotiation, "
            "including relevant market context."
        ),
    },
    "expected_outcome": {
        "type": "string",
        "description": (
            "What you think the counterparty might do next or where the negotiation "
            "may move from here."
        ),
    },
    "approach": {
        "type": "string",
        "description": (
            "A concise description of how you plan to approach this turn."
        ),
    },
    "intended_action": {
        "type": "string",
        "description": (
            "A short statement of the exact action you are about to take."
        ),
    },
}


# --- Claude API tool schemas (passed to the model) ---

NEGOTIATION_TOOLS = [
    {
        "name": "check_market_price",
        "description": (
            "Check the current market reference price for a product. "
            "Note: market data can be noisy and may differ from what other parties see."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "The product to check the price for",
                }
            },
            "required": ["product"],
        },
    },
    {
        "name": "make_offer",
        "description": (
            "Propose a price to the other party. Include a short message, a brief "
            "structured rationale, and the exact action you are taking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {
                    "type": "number",
                    "description": "The price you are proposing",
                },
                "message": {
                    "type": "string",
                    "description": "A short message explaining your offer",
                },
                **RATIONALE_PROPERTIES,
            },
            "required": [
                "price",
                "message",
                "current_state",
                "expected_outcome",
                "approach",
                "intended_action",
            ],
        },
    },
    {
        "name": "accept_offer",
        "description": (
            "Accept the most recent offer from the other party. This closes the deal. "
            "Also include the four-part rationale block and the exact action you are taking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "A short message explaining why you are accepting the offer",
                },
                **RATIONALE_PROPERTIES,
            },
            "required": [
                "message",
                "current_state",
                "expected_outcome",
                "approach",
                "intended_action",
            ],
        },
    },
    {
        "name": "reject_offer",
        "description": (
            "Reject the most recent offer. You can continue negotiating after this. "
            "Include the four-part rationale block and the exact action you are taking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you are rejecting the offer",
                },
                **RATIONALE_PROPERTIES,
            },
            "required": [
                "reason",
                "current_state",
                "expected_outcome",
                "approach",
                "intended_action",
            ],
        },
    },
    {
        "name": "walk_away",
        "description": (
            "End the negotiation entirely. The deal fails. "
            "Use this only when you believe no agreement is possible. "
            "Include the four-part rationale block and the exact action you are taking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you are walking away",
                },
                **RATIONALE_PROPERTIES,
            },
            "required": [
                "reason",
                "current_state",
                "expected_outcome",
                "approach",
                "intended_action",
            ],
        },
    },
]


# --- Tool execution ---

def execute_check_market_price(
    product: str, config: SimulationConfig
) -> dict:
    """Return a noisy market price. Each call produces a different value."""
    ground = config.product.ground_truth_price
    noise = random.gauss(0, config.sigma)
    observed = round(ground + noise, 2)
    return {
        "product": product,
        "market_price": observed,
        "_ground_truth": ground,
        "_noise": round(noise, 2),
    }
