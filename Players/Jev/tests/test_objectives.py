import unittest

from jev_player.objectives import pending_objectives, selected_objectives, target_complete
from jev_player.policy import Policy


def policy(objective):
    return Policy.from_dict({"objective": objective, "fossil": "DOME"})


def snapshot(scene="field", map_id="REDS_HOUSE_2F", flags=()):
    return {
        "scene": scene,
        "field": {"mapID": map_id},
        "eventFlags": {"activeFlags": list(flags)},
    }


class ObjectiveTests(unittest.TestCase):
    def test_oaks_lab_prefix_stops_before_the_rival(self):
        selected = [item.id for item in selected_objectives(policy("oaks_lab"))]
        self.assertEqual(selected, ["oak_intro", "oaks_lab"])
        pending = [item.id for item in pending_objectives(policy("oaks_lab"), snapshot(scene="titleAttract"))]
        self.assertEqual(pending, ["oak_intro", "oaks_lab"])

    def test_oaks_lab_completes_on_the_lab_map(self):
        self.assertTrue(target_complete(policy("oaks_lab"), snapshot(map_id="OAKS_LAB")))
        self.assertFalse(target_complete(policy("oaks_lab"), snapshot(map_id="PALLET_TOWN")))

    def test_cascade_badge_is_the_last_corridor_predicate(self):
        selected = [item.id for item in selected_objectives(policy("misty"))]
        self.assertEqual(selected[-1], "misty")
        self.assertLess(selected.index("brock"), selected.index("mt_moon_fossil"))
        self.assertLess(selected.index("ss_ticket"), selected.index("misty"))
        self.assertFalse(target_complete(policy("misty"), snapshot()))
        self.assertTrue(target_complete(policy("misty"), snapshot(flags=["EVENT_BEAT_MISTY"])))
