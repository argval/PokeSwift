import json
import tempfile
import unittest

from jev_player.client import TelemetryClient
from jev_player.loop import Trace, run_player
from jev_player.policy import Policy
from jev_player.world import World


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ScriptedTransport:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.posts = []

    def get_json(self, path):
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def post_json(self, path, body):
        self.posts.append((path, body))
        return {"accepted": True}


class LoopTests(unittest.TestCase):
    def test_trace_records_the_button_and_stops_at_the_objective(self):
        transport = ScriptedTransport(
            [
                {"scene": "titleAttract", "substate": "attract", "inputReady": True},
                {
                    "scene": "field",
                    "substate": "field",
                    "inputReady": True,
                    "field": {"mapID": "REDS_HOUSE_2F", "playerPosition": {"x": 4, "y": 4}, "facing": "down"},
                },
            ]
        )
        client = TelemetryClient(transport=transport, clock=FakeClock(), timeout=1.0, poll_interval=0.1)
        policy = Policy.from_dict({"objective": "oak_intro"})
        world = World({"maps": [], "tilesets": []})
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            trace_path = handle.name
        trace = Trace(path=trace_path)

        result = run_player(client, policy, world, judge=None, trace=trace, max_steps=5)

        self.assertTrue(result.completed)
        self.assertEqual(result.reason, "complete")
        self.assertEqual(transport.posts, [("/input", {"button": "confirm"})])
        with open(trace_path, encoding="utf-8") as handle:
            lines = [json.loads(line) for line in handle if line.strip()]
        self.assertGreaterEqual(len(lines), 1)
        self.assertEqual(lines[0]["button"], "confirm")
        self.assertEqual(lines[0]["rule"], "policy.title")
        self.assertIn("snapshot", lines[0])
        self.assertEqual(lines[0]["mode"], "field")
