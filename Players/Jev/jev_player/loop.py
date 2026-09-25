"""Drive one button at a time and write a JSONL decision trace."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from jev_player.client import SnapshotTimeout
from jev_player.judge import Judge
from jev_player.objectives import navigation_button, target_complete
from jev_player.router import decide
from jev_player.snapshot import map_id, slim_snapshot, snapshot_identity
from jev_player.world import World


@dataclass
class Trace:
    path: str | None = None
    records: list = field(default_factory=list)

    def write(self, record):
        self.records.append(record)
        if not self.path:
            return
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


@dataclass
class RunResult:
    completed: bool
    reason: str
    snapshot: dict | None = None
    steps: int = 0


@dataclass
class RunMemory:
    previous_map: str | None = None
    last_map: str | None = None

    def observe(self, world, snapshot):
        current = map_id(snapshot)
        if self.last_map and current and current != self.last_map:
            self.previous_map = world.remember_previous(self.last_map, current, self.previous_map)
        if current:
            self.last_map = current


def run_player(
    client,
    policy,
    world,
    judge=None,
    trace=None,
    max_steps=5000,
    idle_limit=40,
):
    if judge is None:
        judge = Judge(
            confidence_floor=policy.jev_confidence_floor,
            noul_threshold=policy.noul_threshold,
        )
    if trace is None:
        trace = Trace()
    memory = RunMemory()
    snapshot = client.wait_until_ready()
    memory.observe(world, snapshot)
    idle = 0
    steps = 0
    last_identity = None

    while steps < max_steps:
        if target_complete(policy, snapshot):
            trace.write(_record(snapshot, "policy.complete", None, None))
            return RunResult(True, "complete", snapshot, steps)
        if not snapshot.get("inputReady", False):
            try:
                snapshot = client.wait_until_ready()
            except SnapshotTimeout:
                trace.write(_record(snapshot, "stall.timeout", None, None))
                return RunResult(False, "timeout", snapshot, steps)
            memory.observe(world, snapshot)
            continue

        decision = decide(snapshot, policy, world, judge)
        if decision is None:
            button, rule = navigation_button(world, snapshot, policy, memory.previous_map)
            jev_payload = None
            target = None
        else:
            button = decision.button
            rule = decision.rule
            jev_payload = decision.jev
            target = decision.target

        if button is None:
            identity = snapshot_identity(snapshot)
            if identity == last_identity:
                idle += 1
            else:
                idle = 0
                last_identity = identity
            if idle >= idle_limit:
                trace.write(_record(snapshot, rule or "stall.idle", jev_payload, None))
                return RunResult(False, "stall", snapshot, steps)
            client.clock.sleep(client.poll_interval)
            try:
                snapshot = client.latest()
            except SnapshotTimeout:
                trace.write(_record(snapshot, "stall.timeout", jev_payload, None))
                return RunResult(False, "timeout", snapshot, steps)
            memory.observe(world, snapshot)
            continue

        before = snapshot
        try:
            snapshot = client.press_and_wait(button, before)
        except SnapshotTimeout:
            trace.write(_record(before, "stall.timeout", jev_payload, button))
            return RunResult(False, "timeout", before, steps)
        steps += 1
        idle = 0
        last_identity = snapshot_identity(snapshot)
        memory.observe(world, snapshot)
        trace.write(_record(snapshot, rule, jev_payload, button, target=target))

    trace.write(_record(snapshot, "stall.max_steps", None, None))
    return RunResult(False, "max_steps", snapshot, steps)


def _record(snapshot, rule, jev_payload, button, target=None):
    return {
        "mode": snapshot.get("scene"),
        "rule": rule,
        "jev": jev_payload,
        "button": button,
        "target": target,
        "snapshot": slim_snapshot(snapshot),
    }


def open_world(content_path=None):
    if content_path:
        return World.load(content_path)
    return World.load()
