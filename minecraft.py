import json
import os
import logging
from collections import defaultdict

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
        self.currentGoal = None
        self.buildPlan = []
        self.completedSteps = set()
        self.currentStep = None
        self.buildVerified = False

        self.tools = self.createTools()

    # ==========================================================
    # TOOL DEFINITIONS
    # ==========================================================

    def createTools(self):
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
                    "name": "craft",
                    "description": (
                        "Craft an item by name. Must have the "
                        "required materials in inventory."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["itemName"],
                        "properties": {
                            "itemName": {"type": "string"},
                        },
                    },
                },
            },
        ]

    # ==========================================================
    # BUILDING MEMORY
    # ==========================================================

    def formatCoordinates(self, x, y, z):
        return f"{x},{y},{z}"

    def recordPlacedBlock(self, blockType, x, y, z):
        coordinates = (
            int(x),
            int(y),
            int(z),
        )

        self.placedBlocks[coordinates] = blockType
        self.buildVerified = False

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
        self.buildVerified = False

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

        blocksByType = defaultdict(int)

        for blockType in self.placedBlocks.values():
            blocksByType[blockType] += 1

        counts = ", ".join(
            f"{blockType}: {count}"
            for blockType, count in blocksByType.items()
        )

        return (
            f"Placed blocks: {len(self.placedBlocks)}. "
            f"Block counts: {counts}"
        )

    def getRecentPlacedBlocks(self, limit=20):
        if not self.placedBlocks:
            return "No placed blocks."

        recentBlocks = list(self.placedBlocks.items())[-limit:]

        return "\n".join(
            f"- {blockType} at "
            f"{self.formatCoordinates(*coordinates)}"
            for coordinates, blockType in recentBlocks
        )

    # ==========================================================
    # BUILD PLAN
    # ==========================================================

    def setBuildingPlan(self, goal, steps=None):
        self.currentGoal = goal
        self.buildPlan = steps or []

        self.completedSteps = set()
        self.currentStep = None
        self.buildVerified = False

        logger.info(
            "BUILD PLAN CREATED goal=%s steps=%s",
            goal,
            self.buildPlan,
        )

    def getBuildingContext(self):
        if not self.currentGoal:
            return "No active building goal."

        plan = "\n".join(
            f"{index + 1}. {step}"
            for index, step in enumerate(self.buildPlan)
        )

        completed = ", ".join(
            str(step)
            for step in sorted(self.completedSteps)
        )

        currentStep = self.currentStep or "Not selected"

        return (
            f"CURRENT BUILDING GOAL: {self.currentGoal}\n"
            f"BUILDING PLAN:\n"
            f"{plan or 'No plan created yet.'}\n"
            f"COMPLETED STEPS: "
            f"{completed or 'None'}\n"
            f"CURRENT STEP: {currentStep}\n"
            f"BUILD VERIFIED: {self.buildVerified}\n"
            f"BUILD MEMORY: {self.getBuildingMemory()}\n"
            f"RECENT PLACEMENTS:\n"
            f"{self.getRecentPlacedBlocks()}"
        )

    # ==========================================================
    # COMPACT TOOL RESULTS
    # ==========================================================

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

        if name == "craft":
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

        if name in {
            "findEntities",
            "findNearbyMonsters",
            "getPlayerSummary",
            "getBlock",
            "follow",
        }:
            return self.compactInformationResult(result)

        if isinstance(result, dict):
            if result.get("ok") is False:
                return (
                    f"tool failed: "
                    f"{result.get('error', 'unknown error')}"
                )

            return "tool completed successfully"

        if isinstance(result, str):
            return result[:500]

        return "tool completed successfully"

    def compactInformationResult(self, result):
        if result is None:
            return "No information returned."

        if isinstance(result, str):
            return result[:1500]

        if isinstance(result, (int, float, bool)):
            return str(result)

        if isinstance(result, list):
            if not result:
                return "No results."

            compactResults = result[:20]

            return json.dumps(
                compactResults,
                default=str,
            )[:3000]

        if isinstance(result, dict):
            if result.get("ok") is False:
                return json.dumps(
                    result,
                    default=str,
                )[:1500]

            usefulKeys = {
                "block",
                "blockName",
                "blockType",
                "name",
                "type",
                "x",
                "y",
                "z",
                "distance",
                "entityType",
                "entities",
                "position",
                "biome",
                "health",
                "hunger",
                "inventory",
            }

            compactResult = {
                key: value
                for key, value in result.items()
                if key in usefulKeys
            }

            if compactResult:
                return json.dumps(
                    compactResult,
                    default=str,
                )[:3000]

            return json.dumps(
                result,
                default=str,
            )[:1500]

        return str(result)[:1500]

    # ==========================================================
    # TOOL EXECUTION
    # ==========================================================

    def callTool(self, name, arguments):
        logger.info(
            "TOOL START name=%s arguments=%s",
            name,
            arguments,
        )

        toolMap = {
            "goto": self.player.goto,
            "mine": self.player.mine,
            "mineBlock": self.player.mineBlock,
            "craft": self.player.craft,
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

        if name not in toolMap:
            return {
                "ok": False,
                "error": f"Unknown tool: {name}",
            }

        try:
            result = toolMap[name](**arguments)

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

    # ==========================================================
    # MINECRAFT CHAT
    # ==========================================================

    def isDirectCommand(self, message):
        return message.split(maxsplit=1)[0] in (
            self.player.commandTemplates
        )

    def executeDirectCommand(self, message):
        self.player.handleChat(message)

    def sendMessage(self, message):
        self.player.sendMessage(message)

    def startChatListener(self, callback):
        listener = ChatListener(
            playerName=self.player.name,
            logFile=os.path.abspath("./logs/latest.log"),
            callback=callback,
        )

        listener.start()

        logger.info(
            "Chat listener started for player %s",
            self.player.name,
        )

        return listener