import unittest

from jev_player.judge import Judge


class JudgeTests(unittest.TestCase):
    def test_low_confidence_choice_is_marked(self):
        def caller(_state, _questions):
            return {
                "choices": {"move": {"choice": "BUBBLE", "confidence": 0.2}},
                "nouls": {"catch": {"noul": 0.95}},
                "scores": {"threat": {"score": "the fight is even", "confidence": 0.8}},
            }

        judge = Judge(caller=caller, confidence_floor=0.45, noul_threshold=0.6)
        parsed = judge.ask(
            {},
            {
                "move": {"kind": "choice", "options": ["WATER_GUN", "BUBBLE"]},
                "catch": {"kind": "noul"},
                "threat": {"kind": "score", "criteria": ["the fight is even"]},
            },
        )
        self.assertTrue(parsed["move"]["low_confidence"])
        self.assertEqual(parsed["move"]["value"], "BUBBLE")
        self.assertTrue(parsed["catch"]["accept"])
        self.assertFalse(parsed["catch"]["low_confidence"])
        self.assertEqual(parsed["threat"]["value"], "the fight is even")

    def test_uncertain_noul_does_not_accept(self):
        def caller(_state, _questions):
            return {"nouls": {"catch": {"noul": 0.55}}}

        judge = Judge(caller=caller, confidence_floor=0.45, noul_threshold=0.6)
        parsed = judge.ask({}, {"catch": {"kind": "noul"}})
        self.assertFalse(parsed["catch"]["accept"])
        self.assertTrue(parsed["catch"]["low_confidence"])
