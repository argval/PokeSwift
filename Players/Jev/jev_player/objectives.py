"""Ordered checklist for the shipped Red corridor. Jev does not invent the next town."""

from __future__ import annotations

from jev_player.snapshot import flag_set, item_count, map_id, party_hp_fraction, position
from jev_player.world import Node

INTRO_SCENES = {
    "launch",
    "splash",
    "titleAttract",
    "titleMenu",
    "titleOptions",
    "oakIntro",
    "placeholder",
}

NURSES = (
    "viridian_pokecenter_nurse",
    "pewter_pokecenter_nurse",
    "cerulean_pokecenter_nurse",
    "mt_moon_pokecenter_nurse",
)

CLERKS = (
    ("viridian_mart_clerk", "EVENT_OAK_GOT_PARCEL"),
    ("pewter_mart_clerk", None),
    ("cerulean_mart_clerk", None),
)

GYM_MAPS = {
    "brock": "PEWTER_GYM",
    "misty": "CERULEAN_GYM",
}


class Objective:
    def __init__(self, objective_id, complete):
        self.id = objective_id
        self._complete = complete

    def complete(self, snapshot, policy):
        return self._complete(snapshot, policy)


def _scene_outside_intro(snapshot, _policy):
    return snapshot.get("scene") not in INTRO_SCENES


def _on_map(target):
    def complete(snapshot, _policy):
        return map_id(snapshot) == target

    return complete


def _flag(flag_id):
    def complete(snapshot, _policy):
        return flag_set(snapshot, flag_id)

    return complete


def _fossil(snapshot, policy):
    if policy.fossil == "HELIX":
        return flag_set(snapshot, "EVENT_GOT_HELIX_FOSSIL")
    return flag_set(snapshot, "EVENT_GOT_DOME_FOSSIL")


OBJECTIVES = (
    Objective("oak_intro", _scene_outside_intro),
    Objective("oaks_lab", _on_map("OAKS_LAB")),
    Objective("starter", _flag("EVENT_GOT_STARTER")),
    Objective("rival", _flag("EVENT_BATTLED_RIVAL_IN_OAKS_LAB")),
    Objective("parcel", _flag("EVENT_GOT_OAKS_PARCEL")),
    Objective("pokedex", _flag("EVENT_GOT_POKEDEX")),
    Objective("brock", _flag("EVENT_BEAT_BROCK")),
    Objective("mt_moon_fossil", _fossil),
    Objective("cerulean_rival", _flag("EVENT_BEAT_CERULEAN_RIVAL")),
    Objective("nugget", _flag("EVENT_GOT_NUGGET")),
    Objective("ss_ticket", _flag("EVENT_GOT_SS_TICKET")),
    Objective("misty", _flag("EVENT_BEAT_MISTY")),
)


def objective_by_id(objective_id):
    for objective in OBJECTIVES:
        if objective.id == objective_id:
            return objective
    raise KeyError(objective_id)


def selected_objectives(policy):
    selected = []
    for objective in OBJECTIVES:
        selected.append(objective)
        if objective.id == policy.objective:
            return selected
    raise KeyError(policy.objective)


def pending_objectives(policy, snapshot):
    return [objective for objective in selected_objectives(policy) if not objective.complete(snapshot, policy)]


def target_complete(policy, snapshot):
    return objective_by_id(policy.objective).complete(snapshot, policy)


def active_objective(policy, snapshot):
    pending = pending_objectives(policy, snapshot)
    if not pending:
        return None
    return pending[0]


def _start_node(snapshot, previous):
    current_map = map_id(snapshot)
    x, y = position(snapshot)
    if current_map is None or x is None or y is None:
        return None
    return Node(current_map, x, y, previous)


def _in_gym(policy, snapshot):
    active = active_objective(policy, snapshot)
    if active is None:
        return False
    gym = GYM_MAPS.get(active.id)
    return gym is not None and map_id(snapshot) == gym


def _needs_heal(policy, snapshot):
    if _in_gym(policy, snapshot):
        return False
    return party_hp_fraction(snapshot) < policy.heal_below_hp_fraction


def _stock_short(policy, snapshot):
    for item_id, target in policy.mart.items():
        if item_count(snapshot, item_id) < int(target):
            return True
    return False


def _needs_shop(policy, snapshot):
    if _in_gym(policy, snapshot) or not _stock_short(policy, snapshot):
        return False
    if flag_set(snapshot, "EVENT_OAK_GOT_PARCEL"):
        return True
    return map_id(snapshot) in {"PEWTER_MART", "CERULEAN_MART"}


def _closest_interact(world, start, snapshot, object_ids):
    best = None
    best_length = None
    for object_id in object_ids:
        if world.object_manifest(object_id) is None:
            continue
        stands = world.stand_tiles(object_id, snapshot=snapshot)
        if not stands:
            continue
        tiles = {(item[1], item[2]) for item in stands}
        path = world.path_to_tiles(start, stands[0][0], tiles, snapshot=snapshot)
        if path is None:
            continue
        if best_length is None or len(path) < best_length:
            best = object_id
            best_length = len(path)
    return best


def _story_goal(world, snapshot, policy, objective):
    if objective.id == "oak_intro":
        return None
    if objective.id == "oaks_lab":
        return ("map", "OAKS_LAB", None)
    if objective.id == "starter":
        species = policy.starter.lower()
        return ("interact", f"oaks_lab_poke_ball_{species}", None)
    if objective.id == "rival":
        tiles = world.walkable_tiles("OAKS_LAB", lambda _x, y: y == 6, snapshot=snapshot)
        return ("tiles", "OAKS_LAB", tiles)
    if objective.id == "parcel":
        return ("map", "VIRIDIAN_MART", None)
    if objective.id == "pokedex":
        return ("interact", "oaks_lab_oak_1", None)
    if objective.id == "brock":
        return ("interact", "pewter_gym_brock", None)
    if objective.id == "mt_moon_fossil":
        fossil = "helix" if policy.fossil == "HELIX" else "dome"
        return ("interact", f"mt_moon_b2f_{fossil}_fossil", None)
    if objective.id == "cerulean_rival":
        return ("tiles", "CERULEAN_CITY", [(20, 6), (21, 6)])
    if objective.id == "nugget":
        return ("tiles", "ROUTE_24", [(10, 15)])
    if objective.id == "ss_ticket":
        return ("interact", "bills_house_bill_pokemon", None)
    if objective.id == "misty":
        return ("interact", "cerulean_gym_misty", None)
    return None


def _button_for_goal(world, start, snapshot, facing, goal):
    if goal is None:
        return None
    kind, target, extra = goal
    if kind == "map":
        if start.map_id == target:
            return None
        path = world.path_to_map(start, target, snapshot=snapshot)
        if not path:
            return None
        return path[0][0]
    if kind == "tiles":
        if start.map_id == target and (start.x, start.y) in set(extra or []):
            for facing_name, (dx, dy) in (
                ("up", (0, -1)),
                ("down", (0, 1)),
                ("left", (-1, 0)),
                ("right", (1, 0)),
            ):
                nxt = (start.x + dx, start.y + dy)
                if world.in_bounds(start.map_id, nxt[0], nxt[1]) and world.tile_passable(start.map_id, nxt[0], nxt[1]):
                    return facing_name
            return None
        path = world.path_to_tiles(start, target, extra or [], snapshot=snapshot)
        if not path:
            return None
        return path[0][0]
    if kind == "interact":
        return world.interact_button(start, target, snapshot, facing)
    return None


def navigation_button(world, snapshot, policy, previous):
    if snapshot.get("scene") != "field":
        return None, "wait.scene"
    if (snapshot.get("field") or {}).get("activeScriptID"):
        return None, "wait.script"
    start = _start_node(snapshot, previous)
    if start is None:
        return None, "stall.position"
    if _needs_heal(policy, snapshot):
        nurse = _closest_interact(world, start, snapshot, NURSES)
        if nurse is not None:
            button = world.interact_button(start, nurse, snapshot, snapshot.get("field", {}).get("facing"))
            if button is not None:
                return button, f"policy.heal.{nurse}"
    if _needs_shop(policy, snapshot):
        clerks = []
        for object_id, required_flag in CLERKS:
            if required_flag is not None and not flag_set(snapshot, required_flag):
                continue
            clerks.append(object_id)
        clerk = _closest_interact(world, start, snapshot, clerks)
        if clerk is not None:
            button = world.interact_button(start, clerk, snapshot, snapshot.get("field", {}).get("facing"))
            if button is not None:
                return button, f"policy.shop.{clerk}"
    objective = active_objective(policy, snapshot)
    if objective is None:
        return None, "policy.complete"
    goal = _story_goal(world, snapshot, policy, objective)
    button = _button_for_goal(world, start, snapshot, (snapshot.get("field") or {}).get("facing"), goal)
    if button is None:
        return None, f"stall.{objective.id}"
    return button, f"policy.route.{objective.id}"
