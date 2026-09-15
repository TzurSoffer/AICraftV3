import os
import logging
import time

from MCBridge import ChatListener, Player


logger = logging.getLogger(__name__)


class MinecraftController:
    """Minecraft interface and persistent building memory."""

    def __init__(self):
        self.player = Player()

        self.craftAbundanceThreshold = 128

        # Persistent world memory.
        self.placedBlocks = {}
        self.brokenBlocks = set()

        # Building state.
        self.buildPlan = []

        self.toolMap = {
            "goto": self.player.goto,
            "mine": self.player.mine,
            "mineBlock": self.player.mineBlock,
            "craftItems": self.player.craftItems,
            "place": self.player.place,
            "attack": self.player.attack,
            "findEntities": self.player.findEntities,
            "findNearbyMonsters": self.player.findNearbyMonsters,
            "getPlayerSummary": self.player.getPlayerSummary,
            "getBlock": self.player.getBlock,
            "follow": self.player.follow,
            "jump": self.player.jump,
            "leftClick": self.player.leftClick,
            "rightClick": self.player.rightClick,
            "drop": self.player.drop,
            "stop": self.player.stop,
            "updateBuildingPlan": self.setBuildingPlan,
        }

    def getTools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "goto",
                    "description": "Move the player to integer coordinates.",
                    "parameters": {
                        "type": "object",
                        "required": ["x", "y", "z"],
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "z": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mine",
                    "description": "Mine the block at integer coordinates.",
                    "parameters": {
                        "type": "object",
                        "required": ["x", "y", "z"],
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "z": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mineBlock",
                    "description": (
                        "Mine a block type until you have the desired "
                        "amount in your inventory."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["total", "blockName"],
                        "properties": {
                            "total": {"type": "integer"},
                            "blockName": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "place",
                    "description": (
                        "Place a block at integer coordinates. "
                        "Do not place a block at a coordinate that "
                        "already contains the desired block. "
                        "Use exact Minecraft block names."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": [
                            "blockType",
                            "x",
                            "y",
                            "z",
                        ],
                        "properties": {
                            "blockType": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "z": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "placeBlocks",
                    "description": (
                        "Place multiple blocks sequentially. Use this "
                        "when two or more placements of the same block are needed. "
                        "Arguments must be strict JSON with no comments."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["blockType", "coordinates"],
                        "properties": {
                            "blockType": {"type": "string"},
                            "coordinates": {
                                "type": "array",
                                "maxItems": 25,
                                "items": {
                                    "type": "object",
                                    "required": ["x", "y", "z"],
                                    "properties": {
                                        "x": {"type": "integer"},
                                        "y": {"type": "integer"},
                                        "z": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mineBlocks",
                    "description": (
                        "Mine multiple blocks sequentially. Use this "
                        "when two or more coordinates are known. "
                        "Arguments must be strict JSON with no comments."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["coordinates"],
                        "properties": {
                            "coordinates": {
                                "type": "array",
                                "maxItems": 25,
                                "items": {
                                    "type": "object",
                                    "required": ["x", "y", "z"],
                                    "properties": {
                                        "x": {"type": "integer"},
                                        "y": {"type": "integer"},
                                        "z": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "attack",
                    "description": "Attack the nearest matching entity.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entityType": {
                                "type": ["string", "null"]
                            },
                            "radius": {
                                "type": "number",
                                "default": 4.5,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "findEntities",
                    "description": (
                        "Find nearby entities, optionally filtered "
                        "by type."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entityType": {
                                "type": ["string", "null"]
                            },
                            "radius": {
                                "type": "number",
                                "default": 32,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "findNearbyMonsters",
                    "description": "Find hostile mobs near the player.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "xRadius": {
                                "type": "number",
                                "default": 15,
                            },
                            "yRadius": {
                                "type": "number",
                                "default": 15,
                            },
                            "zRadius": {
                                "type": "number",
                                "default": 3,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "getPlayerSummary",
                    "description": (
                        "Get the player's current position, biome, "
                        "health, hunger, inventory, and nearby "
                        "world information."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "getBlock",
                    "description": (
                        "Get the exact block at integer coordinates. "
                        "Use this to verify a block before placing "
                        "it or to verify a building."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["x", "y", "z"],
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "z": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "follow",
                    "description": "Follow a player by name.",
                    "parameters": {
                        "type": "object",
                        "required": ["playerName"],
                        "properties": {
                            "playerName": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "simpleAction",
                    "description": (
                        "Perform jump, left click, right click, "
                        "drop, or stop."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["action"],
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "jump",
                                    "leftClick",
                                    "rightClick",
                                    "drop",
                                    "stop",
                                ],
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "craftItems",
                    "description": (
                        "Craft an exact amount of output items. The "
                        "amount is the desired number of items, not the "
                        "number of recipe executions. "
                        "Arguments must be strict JSON with no comments."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["itemName", "amount"],
                        "properties": {
                            "itemName": {"type": "string"},
                            "amount": {"type": "integer", "minimum": 1},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "updateBuildingPlan",
                    "description": (
                        "Update the current building plan. Should be a list of steps needed to complete the current goal."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["plan"],
                        "properties": {
                            "plan": {"type": "string"},
                        },
                    },
                },
            },
        ]

    def formatCoordinates(self, x, y, z):
        return f"{x},{y},{z}"

    def recordPlacedBlock(self, blockType, x, y, z):
        coordinates = (
            int(x),
            int(y),
            int(z),
        )

        self.placedBlocks[coordinates] = blockType

        logger.info(
            "MEMORY PLACE block=%s coordinates=%s",
            blockType,
            coordinates,
        )

    def recordBrokenBlock(self, x, y, z):
        coordinates = (
            int(x),
            int(y),
            int(z),
        )

        self.placedBlocks.pop(coordinates, None)
        self.brokenBlocks.add(coordinates)

        logger.info(
            "MEMORY BREAK coordinates=%s",
            coordinates,
        )

    def isBlockAlreadyPlaced(self, x, y, z):
        coordinates = (
            int(x),
            int(y),
            int(z),
        )

        return coordinates in self.placedBlocks

    def getBuildingMemory(self):
        if not self.placedBlocks:
            return "No blocks placed yet."

        return "\n".join(
            f"- {blockType} at "
            f"{self.formatCoordinates(*coordinates)}"
            for coordinates, blockType in self.placedBlocks.items()
        )

    def setBuildingPlan(self, plan):
        self.buildPlan = plan
        logger.info(f"BUILD PLAN UPDATED {plan}")
        return "Building plan updated."

    def getBuildingPlan(self):
        return self.buildPlan

    def formatToolResult(self, name, arguments, result):
        x = arguments.get("x")
        y = arguments.get("y")
        z = arguments.get("z")

        coordinates = None

        if x is not None and y is not None and z is not None:
            coordinates = self.formatCoordinates(x, y, z)

        if name == "place":
            blockType = arguments.get("blockType", "unknown")

            if coordinates:
                return f"placed {blockType} at {coordinates}"

            return f"placed {blockType}"

        if name == "mine":
            if coordinates:
                return f"broke block at {coordinates}"

            return "broke block"

        if name == "goto":
            if coordinates:
                return f"moved to {coordinates}"

            return "movement completed"

        if name == "mineBlock":
            blockName = arguments.get("blockName", "unknown")
            total = arguments.get("total", 0)

            return f"mined {total} {blockName}"

        if name == "craftItems":
            itemName = arguments.get("itemName", "")

            if str(result).lower().startswith(
                "you do not have"
            ):
                return (
                    f"craft {itemName} FAILED due to "
                    "insufficient materials"
                )

            try:
                inventory = self.player.getInventory()

                currentCount = sum(
                    slot["count"]
                    for slot in inventory.values()
                    if itemName.lower()
                    in str(slot["name"]).lower()
                )

            except Exception:
                currentCount = None

            if (
                currentCount is not None
                and currentCount >= self.craftAbundanceThreshold
            ):
                return (
                    f"You already have {currentCount} {itemName} "
                    "in your inventory - that's more than enough. "
                    "Do not craft more; move on to the next "
                    "building step."
                )

            return (
                f"crafted {itemName}, "
                f"current count: {currentCount}"
            )

        if name == "attack":
            return "attack completed"

        if name == "simpleAction":
            return (
                f"performed "
                f"{arguments.get('action', 'action')}"
            )

        if type(result) == dict:
            if result.get("ok") is False:
                return (
                    f"tool failed: "
                    f"{result.get('error', 'unknown error')}"
                )

            return "tool completed successfully"

        if type(result) == str:
            return result

        return "tool completed successfully"

    def removeArgumentComments(self, value):
        if isinstance(value, dict):
            return {
                key: self.removeArgumentComments(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                self.removeArgumentComments(item)
                for item in value
            ]

        if isinstance(value, str):
            return "\n".join(
                line
                for line in value.splitlines()
                if not line.strip().startswith("/")
            ).strip()

        return value

    def callTool(self, name, arguments):
        arguments = self.removeArgumentComments(arguments)
        logger.info(f"TOOL START name={name} arguments={arguments}")

        if name == "mineBlocks":
            results = [
                self.callTool("mine", coordinates)
                for coordinates in arguments.get("coordinates", [])
            ]
            return "done breaking"

        if name == "craftItems":
            itemName = arguments["itemName"]
            amount = int(arguments["amount"])

            if amount < 1:
                return {
                    "ok": False,
                    "error": "count must be at least 1",
                }

            lastResult = self.player.craftItems(itemName, amount)

            try:
                time.sleep(0.2)  # Allow time for inventory to update
                inventory = self.player.getInventory()
                inventoryCount = sum(
                    slot["count"]
                    for slot in inventory.values()
                    if itemName.lower()
                    in str(slot["name"]).lower()
                )
            except Exception:
                inventoryCount = None

            return {
                "ok": True,
                "requestedAmount": amount,
                "lastResult": lastResult,
                "inventoryCount": inventoryCount,
            }

        if name == "simpleAction":
            name = arguments.pop("action")

        if name == "place":
            x = arguments["x"]
            y = arguments["y"]
            z = arguments["z"]
            blockType = arguments["blockType"]

            coordinates = (
                int(x),
                int(y),
                int(z),
            )

            if self.isBlockAlreadyPlaced(x, y, z):
                existingBlock = self.placedBlocks[coordinates]

                logger.warning(
                    "DUPLICATE PLACEMENT BLOCK=%s "
                    "EXISTING=%s COORDINATES=%s",
                    blockType,
                    existingBlock,
                    coordinates,
                )

                return (
                    f"already placed {existingBlock} at "
                    f"{x},{y},{z}; "
                    "choose another position"
                )

        if name == "placeBlocks":
            blockType = arguments.get("blockType")
            coordinates = arguments.get("coordinates", [])
            failed = []
            for coord in coordinates:
                if self.callTool("place", {"blockType": blockType, **coord}) == "Missing block in inventory. Could not place block.":
                    failed.append(f"({coord['x']}, {coord['y']}, {coord['z']})")
            if failed:
                return "Done placing, but failed to place blocks at the following coordinates due to missing blocks in inventory: " + ", ".join(failed)

            return "done placing"

        if name not in self.toolMap:
            return {
                "ok": False,
                "error": f"Unknown tool: {name}",
            }

        try:
            result = self.toolMap[name](**arguments)

        except Exception as error:
            logger.exception(
                "TOOL ERROR name=%s",
                name,
            )

            return {
                "ok": False,
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

        logger.info(
            "TOOL END name=%s result=%s",
            name,
            result,
        )

        if (
            isinstance(result, str)
            and "timed out" in result.lower()
        ):
            return {
                "ok": False,
                "error": result,
            }

        if name == "place":
            self.recordPlacedBlock(
                arguments["blockType"],
                arguments["x"],
                arguments["y"],
                arguments["z"],
            )

        elif name == "mine":
            self.recordBrokenBlock(
                arguments["x"],
                arguments["y"],
                arguments["z"],
            )

        return self.formatToolResult(
            name,
            arguments,
            result,
        )

    def isDirectCommand(self, message):
        return message.split(maxsplit=1)[0] in (
            self.player.commandTemplates
        )

    def executeDirectCommand(self, message):
        self.player.handleChat(message)

    def sendMessage(self, message):
        self.player.sendMessage(message)

    def startChatListener(self, callback, controlledByPlayerName=None):
        name = controlledByPlayerName
        if controlledByPlayerName is None:
            name = self.player.name
        listener = ChatListener(
            playerName=name,
            logFile=os.path.abspath("./logs/latest.log"),
            callback=callback,
        )

        listener.start()

        logger.info(
            "Chat listener started for player %s",
            name,
        )

        return listener