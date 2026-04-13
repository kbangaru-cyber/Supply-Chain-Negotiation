"""Configuration for the supply chain negotiation simulation."""

from dataclasses import dataclass, field


@dataclass
class ProductConfig:
    name: str
    ground_truth_price: float  # P_ground


@dataclass
class AgentConfig:
    role: str  # "supplier", "manufacturer", "retailer"
    reservation_price: float  # min sell (supplier/mfr) or max buy (mfr/retailer)
    margin: float = 0.0  # only used by manufacturer


@dataclass
class SimulationConfig:
    product: ProductConfig = field(default_factory=lambda: ProductConfig(
        name="steel_coil",
        ground_truth_price=100.0,
    ))
    supplier: AgentConfig = field(default_factory=lambda: AgentConfig(
        role="supplier",
        reservation_price=90.0,  # min sell price
    ))
    manufacturer: AgentConfig = field(default_factory=lambda: AgentConfig(
        role="manufacturer",
        reservation_price=130.0,  # max buy price from supplier side
        margin=15.0,  # required profit margin
    ))
    retailer: AgentConfig = field(default_factory=lambda: AgentConfig(
        role="retailer",
        reservation_price=130.0,  # max buy price
    ))
    sigma: float = 5.0  # noise std dev for market price tool
    max_rounds: int = 10  # per bilateral negotiation
    model: str = "claude-haiku-4-5-20251001"
