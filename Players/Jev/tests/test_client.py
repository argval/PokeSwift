import unittest

from jev_player.client import SnapshotTimeout, TelemetryClient


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


def ready(**overrides):
    snapshot = {
        "scene": "field",
        "substate": "field",
        "inputReady": True,
        "field": {"mapID": "REDS_HOUSE_2F", "playerPosition": {"x": 4, "y": 4}, "facing": "down"},
    }
    snapshot.update(overrides)
    return snapshot


class TelemetryClientTests(unittest.TestCase):
    def test_press_and_wait_ignores_locked_snapshot_until_identity_changes(self):
        before = ready()
        locked = ready(
            inputReady=False,
            field={"mapID": "REDS_HOUSE_2F", "playerPosition": {"x": 4, "y": 5}, "facing": "down"},
        )
        after = ready(
            field={"mapID": "REDS_HOUSE_2F", "playerPosition": {"x": 4, "y": 5}, "facing": "down"},
        )
        transport = ScriptedTransport([locked, after])
        client = TelemetryClient(transport=transport, clock=FakeClock(), timeout=1.0, poll_interval=0.2)

        snapshot = client.press_and_wait("down", before)

        self.assertEqual(transport.posts, [("/input", {"button": "down"})])
        self.assertTrue(snapshot["inputReady"])
        self.assertEqual(snapshot["field"]["playerPosition"]["y"], 5)

    def test_press_and_wait_times_out_when_snapshot_never_moves(self):
        before = ready()
        transport = ScriptedTransport([ready(inputReady=False)])
        clock = FakeClock()
        client = TelemetryClient(transport=transport, clock=clock, timeout=0.5, poll_interval=0.2)

        with self.assertRaises(SnapshotTimeout):
            client.press_and_wait("confirm", before)
        self.assertGreaterEqual(clock.now, 0.5)
