"""Identity and small readers for RuntimeTelemetrySnapshot JSON."""

from __future__ import annotations


def field(snapshot):
    return snapshot.get("field") or {}


def map_id(snapshot):
    return field(snapshot).get("mapID")


def position(snapshot):
    point = field(snapshot).get("playerPosition") or {}
    return point.get("x"), point.get("y")


def facing(snapshot):
    return field(snapshot).get("facing")


def flags(snapshot):
    event_flags = snapshot.get("eventFlags") or {}
    return set(event_flags.get("activeFlags") or [])


def flag_set(snapshot, flag_id):
    return flag_id in flags(snapshot)


def item_count(snapshot, item_id):
    inventory = snapshot.get("inventory") or {}
    for item in inventory.get("items") or []:
        if item.get("itemID") == item_id:
            return int(item.get("quantity") or 0)
    battle = snapshot.get("battle") or {}
    for item in battle.get("bagItems") or []:
        if item.get("itemID") == item_id:
            return int(item.get("quantity") or 0)
    return 0


def party_hp_fraction(snapshot):
    party = (snapshot.get("party") or {}).get("pokemon") or []
    fractions = []
    for pokemon in party:
        maximum = pokemon.get("maxHP") or 0
        if maximum <= 0:
            continue
        fractions.append((pokemon.get("currentHP") or 0) / maximum)
    if not fractions:
        return 1.0
    return min(fractions)


def snapshot_identity(snapshot):
    dialogue = snapshot.get("dialogue") or {}
    prompt = snapshot.get("fieldPrompt") or {}
    battle = snapshot.get("battle") or {}
    shop = snapshot.get("shop") or {}
    oak = snapshot.get("oakIntro") or {}
    nickname = snapshot.get("nicknamePrompt") or {}
    starter = snapshot.get("starterChoice") or {}
    title = snapshot.get("titleMenu") or {}
    healing = snapshot.get("fieldHealing") or {}
    x, y = position(snapshot)
    return (
        snapshot.get("scene"),
        snapshot.get("substate"),
        map_id(snapshot),
        x,
        y,
        facing(snapshot),
        dialogue.get("dialogueID"),
        dialogue.get("pageIndex"),
        prompt.get("interactionID"),
        prompt.get("focusedIndex"),
        battle.get("battleID"),
        battle.get("phase"),
        battle.get("focusedMoveIndex"),
        battle.get("focusedBagItemIndex"),
        battle.get("focusedPartyIndex"),
        shop.get("phase"),
        shop.get("focusedMainMenuIndex"),
        shop.get("focusedItemIndex"),
        shop.get("focusedConfirmationIndex"),
        shop.get("selectedQuantity"),
        oak.get("phase"),
        oak.get("pageIndex"),
        oak.get("focusedIndex"),
        oak.get("isTypingCustomName"),
        nickname.get("speciesID"),
        nickname.get("focusedIndex"),
        starter.get("focusedIndex"),
        title.get("focusedIndex"),
        healing.get("phase"),
        field(snapshot).get("activeScriptID"),
        field(snapshot).get("activeScriptStep"),
        tuple(sorted(flags(snapshot))),
    )


def slim_snapshot(snapshot):
    x, y = position(snapshot)
    battle = snapshot.get("battle") or {}
    return {
        "scene": snapshot.get("scene"),
        "substate": snapshot.get("substate"),
        "inputReady": snapshot.get("inputReady"),
        "mapID": map_id(snapshot),
        "x": x,
        "y": y,
        "facing": facing(snapshot),
        "battlePhase": battle.get("phase"),
        "flags": sorted(flags(snapshot)),
    }


def judgment_state(snapshot):
    battle = snapshot.get("battle") or {}
    enemy = battle.get("enemyPokemon") or {}
    lead = battle.get("playerPokemon") or {}
    prompt = snapshot.get("fieldPrompt") or {}
    return {
        "scene": snapshot.get("scene"),
        "map": map_id(snapshot),
        "flags": sorted(flags(snapshot)),
        "prompt": {
            "id": prompt.get("interactionID"),
            "options": prompt.get("options") or [],
        },
        "battle": {
            "kind": battle.get("kind"),
            "phase": battle.get("phase"),
            "enemySpecies": enemy.get("speciesID"),
            "enemyLevel": enemy.get("level"),
            "enemyHP": enemy.get("currentHP"),
            "leadSpecies": lead.get("speciesID"),
            "leadLevel": lead.get("level"),
            "leadHP": lead.get("currentHP"),
            "leadMaxHP": lead.get("maxHP"),
            "canRun": battle.get("canRun"),
        },
    }
