"""Map manifests, collision, and pathfinding. Jev never picks a direction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DIRECTIONS = ("up", "down", "left", "right")
DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
CONNECTION_DIRECTIONS = {
    "up": "north",
    "down": "south",
    "left": "west",
    "right": "east",
}


@dataclass(frozen=True)
class Node:
    map_id: str
    x: int
    y: int
    previous: str | None = None


def default_manifest_path():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "Content" / "Red" / "gameplay_manifest.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Content/Red/gameplay_manifest.json")


class World:
    def __init__(self, manifest):
        self.maps = {game_map["id"]: game_map for game_map in manifest.get("maps") or []}
        self.tilesets = {}
        for tileset in manifest.get("tilesets") or []:
            collision = tileset.get("collision") or {}
            pairs = set()
            for pair in collision.get("tilePairCollisions") or []:
                pairs.add((pair["fromTileID"], pair["toTileID"]))
            ledges = set()
            for ledge in collision.get("ledges") or []:
                ledges.add((ledge["facing"], ledge["standingTileID"], ledge["ledgeTileID"]))
            self.tilesets[tileset["id"]] = {
                "passable": set(collision.get("passableTileIDs") or []),
                "doors": set(collision.get("doorTileIDs") or []),
                "pairs": pairs,
                "ledges": ledges,
            }
        self.species = {species["id"]: species for species in manifest.get("species") or []}
        self.moves = {move["id"]: move for move in manifest.get("moves") or []}
        chart = {}
        for row in manifest.get("typeEffectiveness") or []:
            chart[(row["attackingType"], row["defendingType"])] = row["multiplier"]
        self.type_chart = chart
        self._warps = {}
        self._objects = {}
        for map_id, game_map in self.maps.items():
            origins = {}
            for warp in game_map.get("warps") or []:
                origin = warp.get("origin") or {}
                origins[(origin.get("x"), origin.get("y"))] = warp
            self._warps[map_id] = origins
            objects = {}
            for obj in game_map.get("objects") or []:
                objects[obj["id"]] = obj
            self._objects[map_id] = objects
        self._hide_on_flag, self._show_on_flag = self._script_visibility(manifest)

    @staticmethod
    def _script_visibility(manifest):
        """Objects a finished script shows or hides once its flag is set.

        Pickup and give steps hide their target when the success flag lands.
        Later visibility steps in that same script apply with the flag, which
        is how the unused fossil disappears after the one you take.
        """
        writes = {}
        for script in manifest.get("scripts") or []:
            armed = []
            for step in script.get("steps") or []:
                action = step.get("action")
                if action in {"promptItemPickup", "giveItem"} and step.get("successFlagID"):
                    flag_id = step["successFlagID"]
                    if flag_id not in armed:
                        armed.append(flag_id)
                    object_id = step.get("objectID")
                    if object_id:
                        writes.setdefault(flag_id, {})[object_id] = False
                    continue
                if action == "setFlag" and step.get("flagID"):
                    flag_id = step["flagID"]
                    if flag_id not in armed:
                        armed.append(flag_id)
                    continue
                if action != "setObjectVisibility" or not step.get("objectID") or not armed:
                    continue
                visible = step.get("visible") is True
                for flag_id in list(armed):
                    writes.setdefault(flag_id, {})[step["objectID"]] = visible
        hide = {}
        show = {}
        for flag_id, objects in writes.items():
            for object_id, visible in objects.items():
                bucket = show if visible else hide
                bucket.setdefault(flag_id, set()).add(object_id)
        return hide, show

    @classmethod
    def load(cls, path=None):
        manifest_path = Path(path) if path else default_manifest_path()
        with manifest_path.open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def species_display_name(self, species_id):
        species = self.species.get(species_id) or {}
        return species.get("displayName") or species_id

    def move_power(self, move_id):
        return int((self.moves.get(move_id) or {}).get("power") or 0)

    def move_type(self, move_id):
        return (self.moves.get(move_id) or {}).get("type") or "NORMAL"

    def type_multiplier(self, attacking_type, defending_type):
        if not defending_type:
            return 10
        return self.type_chart.get((attacking_type, defending_type), 10)

    def effectiveness(self, move_type, species_id):
        species = self.species.get(species_id) or {}
        primary = self.type_multiplier(move_type, species.get("primaryType") or "NORMAL")
        secondary_type = species.get("secondaryType")
        factor = primary / 10
        if secondary_type:
            factor *= self.type_multiplier(move_type, secondary_type) / 10
        return factor

    def object_manifest(self, object_id):
        for objects in self._objects.values():
            if object_id in objects:
                return objects[object_id]
        return None

    def object_map_id(self, object_id):
        for map_id, objects in self._objects.items():
            if object_id in objects:
                return map_id
        return None

    def in_bounds(self, map_id, x, y):
        game_map = self.maps[map_id]
        return 0 <= x < game_map["stepWidth"] and 0 <= y < game_map["stepHeight"]

    def collision_id(self, map_id, x, y):
        if map_id not in self.maps or not self.in_bounds(map_id, x, y):
            return None
        game_map = self.maps[map_id]
        index = y * game_map["stepWidth"] + x
        tiles = game_map.get("stepCollisionTileIDs") or []
        if index >= len(tiles):
            return None
        return tiles[index]

    def _collision(self, map_id):
        tileset_id = self.maps[map_id]["tileset"]
        return self.tilesets.get(tileset_id) or {
            "passable": set(),
            "doors": set(),
            "pairs": set(),
            "ledges": set(),
        }

    def allows_traversal(self, map_id, from_x, from_y, to_x, to_y, facing):
        current = self.collision_id(map_id, from_x, from_y)
        nxt = self.collision_id(map_id, to_x, to_y)
        if current is None or nxt is None:
            return True
        collision = self._collision(map_id)
        ledge = (facing, current, nxt) in collision["ledges"]
        if nxt not in collision["passable"] and not ledge:
            return False
        if (current, nxt) in collision["pairs"] or (nxt, current) in collision["pairs"]:
            return False
        return True

    def tile_passable(self, map_id, x, y):
        tile_id = self.collision_id(map_id, x, y)
        if tile_id is None:
            return False
        return tile_id in self._collision(map_id)["passable"]

    def is_door(self, map_id, x, y):
        tile_id = self.collision_id(map_id, x, y)
        if tile_id is None:
            return False
        return tile_id in self._collision(map_id)["doors"]

    def remember_previous(self, source_map, target_map, current_previous):
        target = self.maps.get(target_map) or {}
        return_ids = {
            warp.get("targetMapID")
            for warp in target.get("warps") or []
            if warp.get("usesPreviousMapTarget")
        }
        if not return_ids:
            return current_previous
        if source_map in return_ids:
            return source_map
        if current_previous in return_ids:
            return current_previous
        return source_map

    def _active_flags(self, snapshot):
        if not snapshot:
            return set()
        event_flags = snapshot.get("eventFlags") or {}
        return set(event_flags.get("activeFlags") or [])

    def _visibility_overrides(self, snapshot):
        hidden = set()
        shown = set()
        for flag_id in self._active_flags(snapshot):
            hidden.update(self._hide_on_flag.get(flag_id) or ())
            shown.update(self._show_on_flag.get(flag_id) or ())
        return hidden, shown

    def occupied_tiles(self, map_id, snapshot):
        if snapshot and (snapshot.get("field") or {}).get("mapID") == map_id:
            occupied = set()
            for obj in (snapshot.get("field") or {}).get("objects") or []:
                point = obj.get("position") or {}
                occupied.add((point.get("x"), point.get("y")))
            return occupied
        hidden, shown = self._visibility_overrides(snapshot)
        occupied = set()
        for obj in (self.maps.get(map_id) or {}).get("objects") or []:
            object_id = obj.get("id")
            visible = obj.get("visibleByDefault", True) is not False
            if object_id in shown:
                visible = True
            if object_id in hidden:
                visible = False
            if not visible:
                continue
            point = obj.get("position") or {}
            occupied.add((point.get("x"), point.get("y")))
        return occupied

    def _landing(self, warp, source_map, previous, occupied_for):
        if warp.get("usesPreviousMapTarget") and previous:
            target_id = previous
        else:
            target_id = warp.get("targetMapID")
        if target_id not in self.maps:
            return None
        target = self.maps[target_id]
        index = warp.get("targetWarpIndex")
        warps = target.get("warps") or []
        if isinstance(index, int) and 0 <= index < len(warps):
            point = warps[index].get("origin") or {}
        else:
            point = warp.get("targetPosition") or {}
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            return None
        occupied = occupied_for(target_id)
        if self.is_door(target_id, x, y):
            below = (x, y + 1)
            if (
                self.in_bounds(target_id, below[0], below[1])
                and self.tile_passable(target_id, below[0], below[1])
                and below not in occupied
            ):
                x, y = below
        next_previous = self.remember_previous(source_map, target_id, previous)
        return Node(target_id, x, y, next_previous)

    def _connection_node(self, map_id, attempted_x, attempted_y, facing, previous, occupied_for):
        game_map = self.maps[map_id]
        direction = CONNECTION_DIRECTIONS[facing]
        connection = next(
            (
                item
                for item in game_map.get("connections") or []
                if item.get("direction") == direction
            ),
            None,
        )
        if connection is None:
            return None
        target_id = connection.get("targetMapID")
        if target_id not in self.maps:
            return None
        target = self.maps[target_id]
        offset = int(connection.get("offset") or 0) * 2
        if facing in ("up", "down"):
            target_x = attempted_x - offset
            if not 0 <= target_x < target["stepWidth"]:
                return None
            if facing == "up":
                target_y = target["stepHeight"] - 1
                origin = (target_x, target["stepHeight"])
            else:
                target_y = 0
                origin = (target_x, -1)
        else:
            target_y = attempted_y - offset
            if not 0 <= target_y < target["stepHeight"]:
                return None
            if facing == "left":
                target_x = target["stepWidth"] - 1
                origin = (target["stepWidth"], target_y)
            else:
                target_x = 0
                origin = (-1, target_y)
        if not self.allows_traversal(target_id, origin[0], origin[1], target_x, target_y, facing):
            return None
        if (target_x, target_y) in occupied_for(target_id):
            return None
        return Node(target_id, target_x, target_y, previous)

    def neighbors(self, node, occupied_for):
        if node.map_id not in self.maps:
            return
        occupied = occupied_for(node.map_id)
        warps = self._warps.get(node.map_id) or {}
        for facing in DIRECTIONS:
            dx, dy = DELTAS[facing]
            nxt_x = node.x + dx
            nxt_y = node.y + dy
            if self.in_bounds(node.map_id, nxt_x, nxt_y):
                if not self.allows_traversal(node.map_id, node.x, node.y, nxt_x, nxt_y, facing):
                    continue
                if (nxt_x, nxt_y) in occupied:
                    continue
                warp = warps.get((nxt_x, nxt_y))
                if warp is not None:
                    landing = self._landing(warp, node.map_id, node.previous, occupied_for)
                    if landing is not None and (landing.map_id, landing.x, landing.y) != (
                        node.map_id,
                        nxt_x,
                        nxt_y,
                    ):
                        yield facing, landing
                    continue
                yield facing, Node(node.map_id, nxt_x, nxt_y, node.previous)
                continue
            connected = self._connection_node(
                node.map_id,
                nxt_x,
                nxt_y,
                facing,
                node.previous,
                occupied_for,
            )
            if connected is not None:
                yield facing, connected

    def find_path(self, start, goal, snapshot=None, occupied_override=None):
        if goal(start):
            return []

        def occupied_for(map_id):
            if occupied_override is not None and map_id in occupied_override:
                return occupied_override[map_id]
            return self.occupied_tiles(map_id, snapshot)

        queue = [start]
        visited = {start}
        previous = {}
        index = 0
        while index < len(queue):
            current = queue[index]
            index += 1
            for facing, nxt in self.neighbors(current, occupied_for):
                if nxt in visited:
                    continue
                visited.add(nxt)
                previous[nxt] = (current, facing)
                if goal(nxt):
                    return self._reconstruct(nxt, previous)
                queue.append(nxt)
        return None

    def _reconstruct(self, goal, previous):
        steps = []
        cursor = goal
        while cursor in previous:
            current, facing = previous[cursor]
            steps.append((facing, cursor))
            cursor = current
        steps.reverse()
        return steps

    def path_to_map(self, start, map_id, snapshot=None):
        return self.find_path(start, lambda node: node.map_id == map_id, snapshot=snapshot)

    def path_to_tiles(self, start, map_id, tiles, snapshot=None):
        goals = set(tiles)

        def reached(node):
            return node.map_id == map_id and (node.x, node.y) in goals

        return self.find_path(start, reached, snapshot=snapshot)

    def stand_tiles(self, object_id, snapshot=None):
        obj = self.object_manifest(object_id)
        map_id = self.object_map_id(object_id)
        if obj is None or map_id is None:
            return []
        point = obj.get("position") or {}
        origin_x = point.get("x")
        origin_y = point.get("y")
        reach = obj.get("interactionReach") or "adjacent"
        occupied = self.occupied_tiles(map_id, snapshot)
        occupied.discard((origin_x, origin_y))
        stands = []
        for facing, (dx, dy) in DELTAS.items():
            if reach == "overCounter":
                stand = (origin_x - (2 * dx), origin_y - (2 * dy))
                middle = (origin_x - dx, origin_y - dy)
                if not self.in_bounds(map_id, stand[0], stand[1]):
                    continue
                if not self.in_bounds(map_id, middle[0], middle[1]):
                    continue
                if self.tile_passable(map_id, middle[0], middle[1]):
                    continue
                if not self.tile_passable(map_id, stand[0], stand[1]):
                    continue
                if stand in occupied:
                    continue
                stands.append((stand, facing))
                continue
            stand = (origin_x - dx, origin_y - dy)
            if not self.in_bounds(map_id, stand[0], stand[1]):
                continue
            if not self.tile_passable(map_id, stand[0], stand[1]):
                continue
            if stand in occupied:
                continue
            if stand in (self._warps.get(map_id) or {}):
                continue
            stands.append((stand, facing))
        return [(map_id, stand[0], stand[1], facing) for stand, facing in stands]

    def interact_button(self, start, object_id, snapshot, player_facing):
        stands = self.stand_tiles(object_id, snapshot=snapshot)
        if not stands:
            return None
        for map_id, x, y, facing in stands:
            if start.map_id == map_id and start.x == x and start.y == y:
                if player_facing == facing:
                    return "confirm"
                return facing
        tiles = {(item[1], item[2]) for item in stands if item[0] == stands[0][0]}
        map_id = stands[0][0]
        path = self.path_to_tiles(start, map_id, tiles, snapshot=snapshot)
        if not path:
            return None
        return path[0][0]

    def walkable_tiles(self, map_id, predicate, snapshot=None):
        game_map = self.maps.get(map_id)
        if game_map is None:
            return []
        occupied = self.occupied_tiles(map_id, snapshot)
        found = []
        for y in range(game_map["stepHeight"]):
            for x in range(game_map["stepWidth"]):
                if not self.tile_passable(map_id, x, y):
                    continue
                if (x, y) in occupied:
                    continue
                if (x, y) in (self._warps.get(map_id) or {}):
                    continue
                if predicate(x, y):
                    found.append((x, y))
        return found
