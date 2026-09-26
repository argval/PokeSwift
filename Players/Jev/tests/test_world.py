import unittest

from jev_player.world import Node, World


def passable_map(map_id, width, height, blocked=(), warps=(), connections=(), objects=(), doors=()):
    collision = []
    for y in range(height):
        for x in range(width):
            collision.append(0 if (x, y) in blocked else 1)
    return {
        "id": map_id,
        "stepWidth": width,
        "stepHeight": height,
        "tileset": "TEST",
        "stepCollisionTileIDs": collision,
        "warps": list(warps),
        "connections": list(connections),
        "objects": list(objects),
    }


def tileset(doors=()):
    return {
        "id": "TEST",
        "collision": {
            "passableTileIDs": [1],
            "doorTileIDs": list(doors),
            "tilePairCollisions": [],
            "ledges": [],
        },
    }


class WorldTests(unittest.TestCase):
    def test_path_walks_around_a_blocked_tile(self):
        world = World(
            {
                "maps": [passable_map("ROOM", 3, 3, blocked={(1, 1)})],
                "tilesets": [tileset()],
            }
        )
        path = world.find_path(Node("ROOM", 0, 0), lambda node: node.x == 2 and node.y == 2)
        self.assertIsNotNone(path)
        self.assertEqual(path[-1][1], Node("ROOM", 2, 2))
        self.assertNotIn((1, 1), [(step[1].x, step[1].y) for step in path])

    def test_warp_edge_lands_on_the_destination(self):
        warp = {
            "id": "door",
            "origin": {"x": 2, "y": 0},
            "targetMapID": "NEXT",
            "targetPosition": {"x": 0, "y": 1},
            "targetFacing": "down",
            "usesPreviousMapTarget": False,
        }
        world = World(
            {
                "maps": [
                    passable_map("ROOM", 3, 1, warps=[warp]),
                    passable_map("NEXT", 2, 2),
                ],
                "tilesets": [tileset()],
            }
        )
        path = world.path_to_map(Node("ROOM", 0, 0), "NEXT")
        self.assertIsNotNone(path)
        self.assertEqual(path[-1][1].map_id, "NEXT")
        self.assertEqual((path[-1][1].x, path[-1][1].y), (0, 1))

    def test_connection_enters_even_when_destination_tile_is_not_passable(self):
        blocked = passable_map("EAST", 1, 1, blocked={(0, 0)})
        world = World(
            {
                "maps": [
                    passable_map(
                        "WEST",
                        2,
                        1,
                        connections=[
                            {
                                "direction": "east",
                                "targetMapID": "EAST",
                                "offset": 0,
                            }
                        ],
                    ),
                    blocked,
                ],
                "tilesets": [tileset()],
            }
        )
        path = world.path_to_map(Node("WEST", 0, 0), "EAST")
        self.assertIsNotNone(path)
        self.assertEqual(path[-1][1], Node("EAST", 0, 0))

    def test_over_counter_stand_confirms_when_already_facing(self):
        nurse = {
            "id": "nurse",
            "position": {"x": 1, "y": 0},
            "interactionReach": "overCounter",
            "visibleByDefault": True,
        }
        # Nurse (1,0), impassable counter (1,1), stand (1,2).
        collision_rows = [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ]
        collision = [tile for row in collision_rows for tile in row]
        world = World(
            {
                "maps": [
                    {
                        "id": "CENTER",
                        "stepWidth": 3,
                        "stepHeight": 3,
                        "tileset": "TEST",
                        "stepCollisionTileIDs": collision,
                        "warps": [],
                        "connections": [],
                        "objects": [nurse],
                    }
                ],
                "tilesets": [tileset()],
            }
        )
        button = world.interact_button(Node("CENTER", 1, 2), "nurse", snapshot=None, player_facing="up")
        self.assertEqual(button, "confirm")

    def test_bedroom_path_reaches_oaks_lab(self):
        world = World.load()
        path = world.path_to_map(Node("REDS_HOUSE_2F", 4, 4), "OAKS_LAB")
        self.assertIsNotNone(path)
        self.assertEqual(path[-1][1].map_id, "OAKS_LAB")
        maps = [step[1].map_id for step in path]
        self.assertIn("REDS_HOUSE_1F", maps)
        self.assertIn("PALLET_TOWN", maps)

    def test_collected_fossil_opens_the_mt_moon_exit_to_cerulean(self):
        world = World.load()
        start = Node("REDS_HOUSE_2F", 4, 4)
        self.assertIsNone(world.path_to_map(start, "CERULEAN_CITY"))
        stands = world.stand_tiles("mt_moon_b2f_dome_fossil")
        fossil_tiles = {(item[1], item[2]) for item in stands}
        fossil_path = world.path_to_tiles(start, "MT_MOON_B2F", fossil_tiles)
        self.assertIsNotNone(fossil_path)
        snapshot = {
            "field": {"mapID": "REDS_HOUSE_2F"},
            "eventFlags": {"activeFlags": ["EVENT_GOT_DOME_FOSSIL"]},
        }
        path = world.path_to_map(start, "CERULEAN_CITY", snapshot=snapshot)
        self.assertIsNotNone(path)
        maps = [step[1].map_id for step in path]
        self.assertIn("MT_MOON_B2F", maps)
        self.assertEqual(path[-1][1].map_id, "CERULEAN_CITY")
        self.assertIsNotNone(world.path_to_map(start, "CERULEAN_GYM", snapshot=snapshot))
        self.assertIsNotNone(world.path_to_map(start, "BILLS_HOUSE", snapshot=snapshot))
