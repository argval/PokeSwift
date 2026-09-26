"""Mechanical scenes stay in code. Jev is asked only for residual choices."""

from __future__ import annotations

from dataclasses import dataclass

from jev_player.judge import THREAT_LEVELS
from jev_player.snapshot import item_count, judgment_state


@dataclass
class Decision:
    button: str | None
    rule: str
    jev: dict | None = None
    target: str | None = None


def decide(snapshot, policy, world, judge):
    if not snapshot.get("inputReady", False):
        return Decision(button=None, rule="wait.lock")
    if snapshot.get("nicknamePrompt"):
        return _nickname(snapshot)
    if snapshot.get("fieldPrompt"):
        return _prompt(snapshot, policy, judge)
    if snapshot.get("shop"):
        return _shop(snapshot, policy)
    if snapshot.get("fieldHealing"):
        return Decision(button=None, rule="wait.healing")

    scene = snapshot.get("scene")
    if scene == "titleAttract":
        return Decision(button="confirm", rule="policy.title")
    if scene == "titleMenu":
        return _title_menu(snapshot)
    if scene in {"titleOptions", "placeholder"}:
        return Decision(button="cancel", rule="policy.back")
    if scene == "oakIntro":
        return _oak_intro(snapshot, policy)
    if scene == "dialogue":
        return Decision(button="confirm", rule="policy.dialogue")
    if scene == "starterChoice":
        return _starter(snapshot, policy, world)
    if scene == "naming":
        return Decision(button="confirm", rule="policy.nickname_default")
    if scene == "evolution":
        if snapshot.get("substate") == "evolution_animating":
            return Decision(button=None, rule="wait.evolution")
        return Decision(button="confirm", rule="policy.evolution")
    if scene == "battle":
        return _battle(snapshot, policy, world, judge)
    if scene == "field":
        return None
    if scene in {"launch", "splash", "scriptedSequence"}:
        return Decision(button=None, rule="wait.scene")
    return Decision(button=None, rule="wait.scene")


def _circular_step(current, target, count, forward="down", backward="up"):
    if current == target:
        return "confirm"
    ahead = (target - current) % count
    behind = (current - target) % count
    if ahead <= behind:
        return forward
    return backward


def _title_menu(snapshot):
    title = snapshot.get("titleMenu") or {}
    entries = title.get("entries") or []
    target = 0
    for index, entry in enumerate(entries):
        if entry.get("id") == "newGame" and entry.get("isEnabled", True):
            target = index
            break
    button = _circular_step(title.get("focusedIndex") or 0, target, max(1, len(entries)))
    return Decision(button=button, rule="policy.new_game", target="newGame")


def _oak_intro(snapshot, policy):
    oak = snapshot.get("oakIntro") or {}
    phase = oak.get("phase")
    if phase in {"namingPlayer", "namingRival"}:
        if oak.get("isTypingCustomName"):
            return Decision(button="cancel", rule="policy.preset_name")
        presets = oak.get("presets") or []
        wanted = policy.player_name if phase == "namingPlayer" else policy.rival_name
        target = _preset_index(presets, wanted)
        focused = oak.get("focusedIndex") or 0
        if focused == target:
            return Decision(button="confirm", rule="policy.preset_name", target=presets[target] if presets else wanted)
        if focused < target:
            return Decision(button="down", rule="policy.preset_name", target=presets[target] if presets else wanted)
        return Decision(button="up", rule="policy.preset_name", target=presets[target] if presets else wanted)
    return Decision(button="confirm", rule="policy.oak_dialogue")


def _preset_index(presets, wanted):
    folded = wanted.casefold()
    for index, preset in enumerate(presets):
        if preset.casefold() == folded and index != 0:
            return index
    if len(presets) > 1:
        return 1
    return 0


def _starter(snapshot, policy, world):
    starter = snapshot.get("starterChoice") or {}
    options = starter.get("options") or []
    display = world.species_display_name(policy.starter)
    target = 0
    for index, option in enumerate(options):
        if option.casefold() == display.casefold() or option.casefold() == policy.starter.casefold():
            target = index
            break
    button = _circular_step(
        starter.get("focusedIndex") or 0,
        target,
        max(1, len(options)),
        forward="right",
        backward="left",
    )
    name = options[target] if options else policy.starter
    return Decision(button=button, rule="policy.starter", target=name)


def _nickname(snapshot):
    prompt = snapshot.get("nicknamePrompt") or {}
    if prompt.get("focusedIndex") == 1:
        return Decision(button="confirm", rule="policy.nickname_default", target="NO")
    return Decision(button="down", rule="policy.nickname_default", target="NO")


def _prompt_target(snapshot, policy, judge):
    prompt = snapshot.get("fieldPrompt") or {}
    options = prompt.get("options") or ["YES", "NO"]
    interaction_id = prompt.get("interactionID") or ""
    scripted = _scripted_prompt_answer(policy, interaction_id, options)
    jev_payload = None
    if scripted is None:
        questions = {
            "prompt": {
                "kind": "choice",
                "instructions": (
                    f"Choose the reply for prompt {interaction_id}. "
                    "Prefer the option that continues the current story objective."
                ),
                "options": options,
            }
        }
        answers = judge.ask(judgment_state(snapshot), questions) if judge is not None else {}
        answer = answers.get("prompt") or {}
        jev_payload = {"prompt": answer, "questions": questions}
        if answer.get("low_confidence") or answer.get("value") not in options:
            scripted = options[0]
            rule = "policy.prompt.fallback"
        else:
            scripted = answer["value"]
            rule = "jev.prompt"
    else:
        rule = "policy.prompt"
    target = options.index(scripted) if scripted in options else 0
    return target, rule, jev_payload, options[target] if options else scripted


def _scripted_prompt_answer(policy, interaction_id, options):
    configured = policy.prompt_answers.get(interaction_id)
    if configured is not None:
        return _match_option(configured, options)
    fossil = policy.fossil.lower()
    if interaction_id == f"mt_moon_b2f_take_{fossil}_fossil_prompt":
        return _match_option("YES", options)
    if policy.accept_item_prompts and interaction_id.endswith("_prompt"):
        return _match_option("YES", options)
    if "pokemon_center" in interaction_id or "healing" in interaction_id:
        return _match_option("YES", options)
    return None


def _match_option(answer, options):
    folded = str(answer).casefold()
    for option in options:
        if option.casefold() == folded:
            return option
    if folded in {"yes", "y", "true"} and options:
        return options[0]
    if folded in {"no", "n", "false"} and len(options) > 1:
        return options[1]
    return options[0] if options else str(answer)


def _prompt(snapshot, policy, judge):
    prompt = snapshot.get("fieldPrompt") or {}
    target, rule, jev_payload, label = _prompt_target(snapshot, policy, judge)
    focused = prompt.get("focusedIndex") or 0
    if focused != target:
        return Decision(button="down", rule=rule, jev=jev_payload, target=label)
    return Decision(button="confirm", rule=rule, jev=jev_payload, target=label)


def _shop(snapshot, policy):
    shop = snapshot["shop"]
    phase = shop.get("phase")
    if phase == "result":
        return Decision(button="confirm", rule="policy.shop")
    if phase == "sellList":
        return Decision(button="cancel", rule="policy.shop")
    if phase == "confirmation":
        if shop.get("focusedConfirmationIndex") != 0:
            return Decision(button="up", rule="policy.shop")
        return Decision(button="confirm", rule="policy.shop")
    needed = _next_purchase(snapshot, policy, shop)
    if phase == "mainMenu":
        target = 0 if needed is not None else 2
        button = _circular_step(shop.get("focusedMainMenuIndex") or 0, target, 3)
        label = "BUY" if needed is not None else "QUIT"
        return Decision(button=button, rule="policy.shop", target=label)
    if phase == "quantity":
        if needed is None:
            return Decision(button="cancel", rule="policy.shop")
        item_id, _wanted = needed
        return Decision(button="confirm", rule="policy.shop", target=item_id)
    if phase == "buyList":
        if needed is None:
            return Decision(button="cancel", rule="policy.shop")
        item_id, _wanted = needed
        rows = shop.get("buyItems") or []
        target = 0
        for index, row in enumerate(rows):
            if row.get("itemID") == item_id:
                target = index
                break
        button = _circular_step(shop.get("focusedItemIndex") or 0, target, max(1, len(rows)))
        return Decision(button=button, rule="policy.shop", target=item_id)
    return Decision(button="cancel", rule="policy.shop")


def _next_purchase(snapshot, policy, shop):
    rows = {row.get("itemID"): row for row in shop.get("buyItems") or []}
    for item_id, target in policy.mart.items():
        owned = item_count(snapshot, item_id)
        row = rows.get(item_id)
        if row is not None:
            owned = max(owned, int(row.get("ownedQuantity") or 0))
            if not row.get("isSelectable", True):
                continue
        if owned < int(target):
            return item_id, int(target) - owned
    return None


def _battle(snapshot, policy, world, judge):
    battle = snapshot.get("battle") or {}
    phase = battle.get("phase")
    if phase == "introText":
        return Decision(button=None, rule="wait.intro_text")
    if phase in {"turnText", "resolvingTurn", "battleComplete"}:
        return Decision(button="confirm", rule="policy.battle_text")
    if phase == "trainerAboutToUseDecision":
        if battle.get("focusedMoveIndex") != 1:
            return Decision(button="down", rule="policy.no_switch", target="NO")
        return Decision(button="confirm", rule="policy.no_switch", target="NO")
    if phase == "learnMoveDecision":
        if battle.get("focusedMoveIndex") != 0:
            return Decision(button="up", rule="policy.learn_move", target="YES")
        return Decision(button="confirm", rule="policy.learn_move", target="YES")
    if phase == "learnMoveSelection":
        return _learn_move_selection(battle, world)
    if phase == "partySelection":
        return _party_selection(snapshot, battle)
    if phase == "bagSelection":
        return _bag_selection(battle, policy.ball_item_id)
    if phase == "moveSelection":
        return _move_selection(snapshot, policy, world, judge, battle)
    return Decision(button="confirm", rule="policy.battle_text")


def _battle_actions(battle):
    actions = [("move", index) for index, _slot in enumerate(battle.get("moveSlots") or [])]
    if battle.get("canUseBag"):
        actions.append(("bag", None))
    if battle.get("canSwitch"):
        actions.append(("switch", None))
    if battle.get("canRun"):
        actions.append(("run", None))
    return actions


def _focus_action(battle, target_index, rule, jev_payload, target):
    current = battle.get("focusedMoveIndex") or 0
    if current == target_index:
        return Decision(button="confirm", rule=rule, jev=jev_payload, target=target)
    if current > target_index:
        return Decision(button="up", rule=rule, jev=jev_payload, target=target)
    return Decision(button="down", rule=rule, jev=jev_payload, target=target)


def _selectable_moves(battle):
    selected = []
    for index, slot in enumerate(battle.get("moveSlots") or []):
        if slot.get("isSelectable", True):
            selected.append((index, slot))
    return selected


def _first_damaging_index(world, slots):
    for index, slot in slots:
        if world.move_power(slot.get("moveID")) > 0:
            return index, slot.get("moveID")
    if slots:
        return slots[0][0], slots[0][1].get("moveID")
    return None, None


def _highest_power_index(world, slots):
    best = None
    best_power = -1
    for index, slot in slots:
        power = world.move_power(slot.get("moveID"))
        if power > best_power:
            best = (index, slot.get("moveID"))
            best_power = power
    if best is None:
        return None, None
    return best


def _super_effective(world, slots, species_id):
    found = []
    for index, slot in slots:
        move_id = slot.get("moveID")
        power = world.move_power(move_id)
        if power <= 0:
            continue
        if world.effectiveness(world.move_type(move_id), species_id) > 1:
            found.append((index, move_id, power))
    return found


def _move_selection(snapshot, policy, world, judge, battle):
    slots = _selectable_moves(battle)
    actions = _battle_actions(battle)
    enemy = (battle.get("enemyPokemon") or {}).get("speciesID")
    preference = policy.battle_preference
    questions = {}
    catch = _catch_candidate(snapshot, policy, battle)
    if catch:
        questions["catch"] = {
            "kind": "noul",
            "instructions": (
                f"Catch this wild {enemy} given the policy catch list {policy.catch_species} "
                f"and {item_count(snapshot, policy.ball_item_id)} {policy.ball_item_id} remaining? "
                "Yes means spend a ball now."
            ),
        }
    candidates = _super_effective(world, slots, enemy) if preference in {"super_effective", "adaptive"} else []
    if preference == "adaptive":
        questions["threat"] = {
            "kind": "score",
            "instructions": "How threatening is this trainer or wild battle relative to the lead?",
            "criteria": list(THREAT_LEVELS),
        }
    if len(candidates) > 1 and preference in {"super_effective", "adaptive"}:
        questions["move"] = {
            "kind": "choice",
            "instructions": "Which super-effective move should the lead use?",
            "options": [move_id for _index, move_id, _power in candidates],
        }
    answers = judge.ask(judgment_state(snapshot), questions) if questions and judge is not None else {}
    jev_payload = {"answers": answers, "questions": questions} if questions else None

    catch_answer = answers.get("catch") or {}
    if catch and catch_answer.get("accept") and not catch_answer.get("low_confidence"):
        bag_index = _action_index(actions, "bag")
        if bag_index is not None:
            return _focus_action(battle, bag_index, "jev.catch", jev_payload, policy.ball_item_id)

    threat = answers.get("threat") or {}
    if (
        preference == "adaptive"
        and threat.get("value") == THREAT_LEVELS[-1]
        and not threat.get("low_confidence")
        and battle.get("canRun")
    ):
        run_index = _action_index(actions, "run")
        if run_index is not None:
            return _focus_action(battle, run_index, "jev.run", jev_payload, "run")

    move_index, move_id, rule = _scripted_move(world, slots, candidates, preference, answers.get("move") or {})
    if move_index is None:
        return Decision(button="confirm", rule="policy.battle_text", jev=jev_payload)
    return _focus_action(battle, move_index, rule, jev_payload, move_id)


def _scripted_move(world, slots, candidates, preference, move_answer):
    if preference == "first_damaging":
        index, move_id = _first_damaging_index(world, slots)
        return index, move_id, "policy.first_damaging"
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], "policy.super_effective"
    if len(candidates) > 1:
        if move_answer and not move_answer.get("low_confidence"):
            chosen = move_answer.get("value")
            for index, move_id, _power in candidates:
                if move_id == chosen:
                    return index, move_id, "jev.move"
        return candidates[0][0], candidates[0][1], "policy.super_effective.fallback"
    index, move_id = _highest_power_index(world, slots)
    rule = "policy.super_effective" if preference != "first_damaging" else "policy.first_damaging"
    return index, move_id, rule


def _catch_candidate(snapshot, policy, battle):
    if battle.get("kind") != "wild":
        return False
    if not battle.get("canUseBag"):
        return False
    species = (battle.get("enemyPokemon") or {}).get("speciesID")
    if species not in set(policy.catch_species):
        return False
    return item_count(snapshot, policy.ball_item_id) > 0


def _action_index(actions, kind):
    for index, (action_kind, _payload) in enumerate(actions):
        if action_kind == kind:
            return index
    return None


def _bag_selection(battle, ball_item_id):
    items = battle.get("bagItems") or []
    target = None
    for index, item in enumerate(items):
        if item.get("itemID") == ball_item_id:
            target = index
            break
    if target is None:
        return Decision(button="cancel", rule="policy.bag_cancel")
    focused = battle.get("focusedBagItemIndex") or 0
    if focused == target:
        return Decision(button="confirm", rule="policy.throw_ball", target=ball_item_id)
    focused_row, focused_column = divmod(focused, 4)
    target_row, target_column = divmod(target, 4)
    if focused_row != target_row:
        button = "down" if target_row > focused_row else "up"
    else:
        button = "right" if target_column > focused_column else "left"
    return Decision(button=button, rule="policy.throw_ball", target=ball_item_id)


def _party_selection(snapshot, battle):
    lead = battle.get("playerPokemon") or {}
    forced = (lead.get("currentHP") or 0) <= 0
    if not forced:
        return Decision(button="cancel", rule="policy.no_switch")
    party = (snapshot.get("party") or {}).get("pokemon") or []
    target = 0
    for index, pokemon in enumerate(party):
        if (pokemon.get("currentHP") or 0) > 0:
            target = index
            break
    focused = battle.get("focusedPartyIndex") or 0
    if focused == target:
        return Decision(button="confirm", rule="policy.forced_switch")
    if focused < target:
        return Decision(button="down", rule="policy.forced_switch")
    return Decision(button="up", rule="policy.forced_switch")


def _learn_move_selection(battle, world):
    slots = battle.get("moveSlots") or []
    if not slots:
        return Decision(button="confirm", rule="policy.learn_move")
    worst = 0
    worst_power = None
    for index, slot in enumerate(slots):
        power = world.move_power(slot.get("moveID"))
        if worst_power is None or power < worst_power:
            worst = index
            worst_power = power
    focused = battle.get("focusedMoveIndex") or 0
    if focused == worst:
        return Decision(button="confirm", rule="policy.learn_move")
    if focused < worst:
        return Decision(button="down", rule="policy.learn_move")
    return Decision(button="up", rule="policy.learn_move")
