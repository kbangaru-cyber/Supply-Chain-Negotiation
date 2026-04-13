"""CLI entry point — run supply chain simulations."""

import argparse
import os
import sys
from dotenv import load_dotenv
from anthropic import Anthropic

from config import SimulationConfig, ProductConfig, AgentConfig
from simulation import run_supply_chain

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run supply chain negotiation simulations")
    parser.add_argument("--runs", type=int, default=1, help="Number of simulation runs")
    parser.add_argument("--sigma", type=float, default=5.0, help="Noise std dev for market prices")
    parser.add_argument("--product", type=str, default="steel_coil", help="Product name")
    parser.add_argument("--price", type=float, default=100.0, help="Ground truth price")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max rounds per negotiation")
    parser.add_argument("--supplier-min", type=float, default=90.0, help="Supplier min sell price")
    parser.add_argument("--mfr-max-buy", type=float, default=130.0, help="Manufacturer max buy price")
    parser.add_argument("--mfr-margin", type=float, default=15.0, help="Manufacturer required margin")
    parser.add_argument("--retailer-max", type=float, default=130.0, help="Retailer max buy price")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Copy .env.example to .env and fill in your key.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    config = SimulationConfig(
        product=ProductConfig(name=args.product, ground_truth_price=args.price),
        supplier=AgentConfig(role="supplier", reservation_price=args.supplier_min),
        manufacturer=AgentConfig(role="manufacturer", reservation_price=args.mfr_max_buy, margin=args.mfr_margin),
        retailer=AgentConfig(role="retailer", reservation_price=args.retailer_max),
        sigma=args.sigma,
        max_rounds=args.max_rounds,
    )

    print(f"Running {args.runs} simulation(s)...")
    print(f"  Product: {args.product} @ ${args.price:.2f} (sigma={args.sigma})")
    print(f"  Supplier min: ${args.supplier_min:.2f}")
    print(f"  Manufacturer max buy: ${args.mfr_max_buy:.2f}, margin: ${args.mfr_margin:.2f}")
    print(f"  Retailer max: ${args.retailer_max:.2f}")
    print()

    results = []
    for i in range(args.runs):
        print(f"--- Run {i + 1}/{args.runs} ---")
        run_record = run_supply_chain(client, config)
        results.append(run_record)
        print(f"  Outcome: {run_record['overall_outcome']}")

        sm = run_record.get("supplier_manufacturer")
        if sm and sm["outcome"] == "success":
            print(f"  S↔M price: ${sm['final_price']:.2f} ({sm['rounds']} rounds)")
        elif sm:
            print(f"  S↔M: FAILED ({sm.get('failure_reason', '?')}, {sm['rounds']} rounds)")

        mr = run_record.get("manufacturer_retailer")
        if mr and mr["outcome"] == "success":
            print(f"  M↔R price: ${mr['final_price']:.2f} ({mr['rounds']} rounds)")
        elif mr:
            print(f"  M↔R: FAILED ({mr.get('failure_reason', '?')}, {mr['rounds']} rounds)")
        print()

    # Summary
    successes = sum(1 for r in results if r["overall_outcome"] == "success")
    print(f"=== Summary: {successes}/{len(results)} runs succeeded ===")


if __name__ == "__main__":
    main()
