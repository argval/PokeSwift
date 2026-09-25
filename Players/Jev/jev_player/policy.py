"""Run parameters. Jev does not invent these."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Policy:
    objective: str = "misty"
    player_name: str = "RED"
    rival_name: str = "BLUE"
    starter: str = "SQUIRTLE"
    heal_below_hp_fraction: float = 0.35
    catch_species: list = field(default_factory=list)
    ball_item_id: str = "POKE_BALL"
    mart: dict = field(default_factory=dict)
    battle_preference: str = "first_damaging"
    fossil: str = "DOME"
    prompt_answers: dict = field(default_factory=dict)
    jev_confidence_floor: float = 0.45
    noul_threshold: float = 0.6
    accept_item_prompts: bool = True

    @classmethod
    def from_dict(cls, payload):
        catch = payload.get("catch") or {}
        battle = payload.get("battle") or {}
        return cls(
            objective=payload.get("objective", "misty"),
            player_name=payload.get("playerName", "RED"),
            rival_name=payload.get("rivalName", "BLUE"),
            starter=payload.get("starter", "SQUIRTLE"),
            heal_below_hp_fraction=float(payload.get("healBelowHpFraction", 0.35)),
            catch_species=list(catch.get("species") or []),
            ball_item_id=catch.get("ballItemID", "POKE_BALL"),
            mart=dict(payload.get("mart") or {}),
            battle_preference=battle.get("preference", "first_damaging"),
            fossil=payload.get("fossil", "DOME"),
            prompt_answers=dict(payload.get("promptAnswers") or {}),
            jev_confidence_floor=float(payload.get("jevConfidenceFloor", 0.45)),
            noul_threshold=float(payload.get("noulThreshold", 0.6)),
            accept_item_prompts=bool(payload.get("acceptItemPrompts", True)),
        )

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
