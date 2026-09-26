import unittest

from jev_player.judge import Judge
from jev_player.policy import Policy
from jev_player.router import decide
from jev_player.world import World


def world():
    return World(
        {
            "maps": [],
            "tilesets": [],
            "species": [
                {"id": "SQUIRTLE", "displayName": "Squirtle", "primaryType": "WATER"},
                {"id": "CHARMANDER", "displayName": "Charmander", "primaryType": "FIRE"},
                {"id": "RATTATA", "displayName": "Rattata", "primaryType": "NORMAL"},
            ],
            "moves": [
                {"id": "TACKLE", "displayName": "Tackle", "power": 35, "type": "NORMAL"},
                {"id": "WATER_GUN", "displayName": "Water Gun", "power": 40, "type": "WATER"},
                {"id": "BUBBLE", "displayName": "Bubble", "power": 20, "type": "WATER"},
            ],
            "typeEffectiveness": [
                {"attackingType": "WATER", "defendingType": "FIRE", "multiplier": 20},
            ],
        }
    )


def policy(**overrides):
    payload = {
        "objective": "rival",
        "playerName": "RED",
        "rivalName": "BLUE",
        "starter": "SQUIRTLE",
        "battle": {"preference": "first_damaging"},
        "catch": {"species": ["RATTATA"], "ballItemID": "POKE_BALL"},
        "promptAnswers": {"known_prompt": "NO"},
        "acceptItemPrompts": True,
        "fossil": "DOME",
    }
    payload.update(overrides)
    return Policy.from_dict(payload)


def battle_snapshot(**battle):
    base = {
        "phase": "moveSelection",
        "kind": "trainer",
        "focusedMoveIndex": 0,
        "focusedBagItemIndex": 0,
        "focusedPartyIndex": 0,
        "canRun": False,
        "canUseBag": False,
        "canSwitch": False,
        "enemyPokemon": {"speciesID": "RATTATA", "level": 5, "currentHP": 18},
        "playerPokemon": {"speciesID": "SQUIRTLE", "level": 5, "currentHP": 20, "maxHP": 20},
        "moveSlots": [
            {"moveID": "TACKLE", "isSelectable": True, "currentPP": 35},
        ],
        "bagItems": [],
    }
    base.update(battle)
    return {"scene": "battle", "inputReady": True, "battle": base, "inventory": {"items": []}}


class RouterTests(unittest.TestCase):
    def test_title_attract_confirms(self):
        decision = decide({"scene": "titleAttract", "inputReady": True}, policy(), world(), None)
        self.assertEqual(decision.button, "confirm")
        self.assertEqual(decision.rule, "policy.title")

    def test_oak_preset_moves_toward_policy_name(self):
        snapshot = {
            "scene": "oakIntro",
            "inputReady": True,
            "oakIntro": {
                "phase": "namingPlayer",
                "presets": ["NEW NAME", "RED", "ASH", "JACK"],
                "focusedIndex": 0,
                "isTypingCustomName": False,
            },
        }
        decision = decide(snapshot, policy(), world(), None)
        self.assertEqual(decision.button, "down")
        self.assertEqual(decision.target, "RED")

    def test_starter_focuses_policy_species(self):
        snapshot = {
            "scene": "starterChoice",
            "inputReady": True,
            "starterChoice": {
                "options": ["Charmander", "Squirtle", "Bulbasaur"],
                "focusedIndex": 0,
            },
        }
        decision = decide(snapshot, policy(), world(), None)
        self.assertEqual(decision.button, "right")
        self.assertEqual(decision.target, "Squirtle")

    def test_first_damaging_move_confirms_without_jev(self):
        def forbid(*_args, **_kwargs):
            raise AssertionError("Jev should not be called")

        judge = Judge(caller=forbid)
        decision = decide(battle_snapshot(), policy(), world(), judge)
        self.assertEqual(decision.button, "confirm")
        self.assertEqual(decision.rule, "policy.first_damaging")
        self.assertEqual(decision.target, "TACKLE")

    def test_policy_prompt_answer_skips_jev(self):
        def forbid(*_args, **_kwargs):
            raise AssertionError("Jev should not be called")

        snapshot = {
            "scene": "dialogue",
            "inputReady": True,
            "fieldPrompt": {
                "interactionID": "known_prompt",
                "options": ["YES", "NO"],
                "focusedIndex": 0,
            },
        }
        decision = decide(snapshot, policy(), world(), Judge(caller=forbid))
        self.assertEqual(decision.button, "down")
        self.assertEqual(decision.target, "NO")
        self.assertEqual(decision.rule, "policy.prompt")

    def test_catch_opens_the_bag_when_noul_accepts(self):
        def caller(_state, _questions):
            return {"nouls": {"catch": {"noul": 0.91}}}

        snapshot = battle_snapshot(
            kind="wild",
            canUseBag=True,
            canRun=True,
            enemyPokemon={"speciesID": "RATTATA", "level": 3, "currentHP": 12},
            bagItems=[{"itemID": "POKE_BALL", "quantity": 2}],
        )
        snapshot["inventory"] = {"items": [{"itemID": "POKE_BALL", "quantity": 2}]}
        decision = decide(snapshot, policy(), world(), Judge(caller=caller, confidence_floor=0.45, noul_threshold=0.6))
        self.assertEqual(decision.rule, "jev.catch")
        self.assertEqual(decision.button, "down")
        self.assertIsNotNone(decision.jev)

    def test_low_confidence_super_effective_choice_uses_the_first_qualifying_move(self):
        def caller(_state, _questions):
            return {"choices": {"move": {"choice": "BUBBLE", "confidence": 0.1}}}

        snapshot = battle_snapshot(
            enemyPokemon={"speciesID": "CHARMANDER", "level": 5, "currentHP": 20},
            moveSlots=[
                {"moveID": "TACKLE", "isSelectable": True},
                {"moveID": "WATER_GUN", "isSelectable": True},
                {"moveID": "BUBBLE", "isSelectable": True},
            ],
        )
        chosen = policy(**{"battle": {"preference": "super_effective"}})
        decision = decide(snapshot, chosen, world(), Judge(caller=caller, confidence_floor=0.45))
        self.assertEqual(decision.target, "WATER_GUN")
        self.assertEqual(decision.rule, "policy.super_effective.fallback")
        self.assertEqual(decision.button, "down")
        self.assertIsNotNone(decision.jev)
