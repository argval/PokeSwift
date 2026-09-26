"""Play the shipped Red corridor against a running PokeMac."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jev_player.client import TelemetryClient
from jev_player.env import load_player_env
from jev_player.judge import Judge
from jev_player.loop import Trace, open_world, run_player
from jev_player.policy import Policy


def main(argv=None):
    load_player_env()
    parser = argparse.ArgumentParser(description="Drive PokeMac from the Jev policy.")
    parser.add_argument("--policy", default=str(Path(__file__).resolve().parents[1] / "policy.json"))
    parser.add_argument("--content", default=None, help="Path to gameplay_manifest.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:9777")
    parser.add_argument("--trace", default="jev-trace.jsonl")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--max-steps", type=int, default=5000)
    args = parser.parse_args(argv)

    policy = Policy.load(args.policy)
    world = open_world(args.content)
    client = TelemetryClient(base_url=args.base_url, timeout=args.timeout)
    judge = Judge(confidence_floor=policy.jev_confidence_floor, noul_threshold=policy.noul_threshold)
    trace = Trace(path=args.trace)
    result = run_player(
        client,
        policy,
        world,
        judge=judge,
        trace=trace,
        max_steps=args.max_steps,
    )
    print(f"{result.reason} steps={result.steps} map={(result.snapshot or {}).get('field', {}).get('mapID')}")
    return 0 if result.completed else 1


if __name__ == "__main__":
    sys.exit(main())
