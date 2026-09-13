import json
import logging
import os
import shlex
import time

from ollama import Client

from MCBridge import ChatListener, Player


MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
# OLLAMA_THINK = True#os.getenv("OLLAMA_THINK", "false").lower() in {"1", "true", "yes"}
MAX_OUTPUT_TOKENS = int(os.getenv("OLLAMA_MAX_OUTPUT_TOKENS", "256"))
EMPTY_RESPONSE_RETRIES = int(os.getenv("OLLAMA_EMPTY_RESPONSE_RETRIES", "2"))
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aicraft.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

class OllamaAgent:
    def __init__(self, player, model=MODEL):
        self.player = player
        self.model = model
        self.ollama = Client(host=OLLAMA_HOST, timeout=OLLAMA_REQUEST_TIMEOUT)
        self.messages = []
        self.additional_context() #< must be here to not be removed by remove_last_context() before the first user message
        self.tools = [
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
                    "description": "Mine the this block until you have the desired amount in your inventory.",
                    "parameters": {
                        "type": "object",
                        "required": ["total", "blockName"],
                        "properties": {
                            "total": {"type": "integer"},
                            "blockName": {"type": "string"}
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "place",
                    "description": "Place a block at integer coordinates.",
                    "parameters": {
                        "type": "object",
                        "required": ["blockType", "x", "y", "z"],
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
                            "entityType": {"type": ["string", "null"]},
                            "radius": {"type": "number", "default": 4.5},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "findEntities",
                    "description": "Find nearby entities, optionally filtered by type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entityType": {"type": ["string", "null"]},
                            "radius": {"type": "number", "default": 32},
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
                            "xRadius": {"type": "number", "default": 15},
                            "yRadius": {"type": "number", "default": 15},
                            "zRadius": {"type": "number", "default": 3},
                        },
                    },
                },
            },
            # {
            # 	"type": "function",
            # 	"function": {
            # 		"name": "getPlayerSummary",
            # 		"description": "Get position, biome, health, hunger, inventory, and nearby monsters.",
            # 		"parameters": {"type": "object", "properties": {}},
            # 	},
            # },
            # {
            #     "type": "function",
            #     "function": {
            #         "name": "getBlock",
            #         "description": "Get the block at integer coordinates.",
            #         "parameters": {
            #             "type": "object",
            #             "required": ["x", "y", "z"],
            #             "properties": {
            #                 "x": {"type": "integer"},
            #                 "y": {"type": "integer"},
            #                 "z": {"type": "integer"},
            #             },
            #         },
            #     },
            # },
            # {
            # 	"type": "function",
            # 	"function": {
            # 		"name": "follow",
            # 		"description": "Follow a player by name.",
            # 		"parameters": {
            # 			"type": "object",
            # 			"required": ["playerName"],
            # 			"properties": {"playerName": {"type": "string"}},
            # 		},
            # 	},
            # },
            {
                "type": "function",
                "function": {
                    "name": "simpleAction",
                    "description": "Perform jump, left click, right click, drop, or stop.",
                    "parameters": {
                        "type": "object",
                        "required": ["action"],
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["jump", "leftClick", "rightClick", "drop", "stop"],
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "craft",
                    "description": "Craft an item by name. Must have the required materials in inventory.",
                    "parameters": {
                        "type": "object",
                        "required": ["itemName"],
                        "properties": {
                            "itemName": {"type": "string"},
                        },
                    },
                },
            }
        ]

    def _call_tool(self, name, arguments):
        logger.info("TOOL START name=%s arguments=%s", name, arguments)
        tool_map = {
            "goto": self.player.goto,
            "mine": self.player.mine,
            "mineBlock": self.player.mineBlock,  #< same function as mine, but with different parameters
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

        try:
            result = tool_map[name](**arguments)
        except Exception as error:
            logger.exception("TOOL ERROR name=%s", name)
            return {
                "ok": False,
                "error": f"{type(error).__name__}: {error}",
            }

        logger.info("TOOL END name=%s result=%s", name, result)
        if isinstance(result, str) and "timed out" in result.lower():
            return {"ok": False, "error": result}
        return result if result is not None else {"ok": True}

    def additional_context(self, currentGoal="You dont have any current goals."):
        self.messages.append({
            "role": "system",
            "content": (
                "[AICRAFT_WORLD_CONTEXT] "
                "Here is information some information about the player and the world: "
                + json.dumps(self.player.getPlayerSummary(), default=str)
            ),
        })
        self.messages.append({
            "role": "system",
            "content": (
                "[AICRAFT_PLANNER_CONTEXT] "
                "You are a Minecraft assistant playing on version 26.2. Use the available tools to "
                "perform actions in the world. Never invent tool results. "
                "After using tools, briefly explain what happened."
                "If the tool you need is not available, explain that you cannot perform the action or use an alternative tool. "
                "When referencing blocks in tools, use the exact block tag including namespace, e.g. minecraft:stone, minecraft:oak_log, etc."
                "You are also a multi-step planner. If the user asks you to do something that requires multiple steps, you should plan out the steps and then execute them one by one."
                "Call exactly one tool per response. Wait for its result before choosing the next tool."
                "Your current goal is: " + currentGoal
            ),
        })

    def remove_last_context(self):
        context_markers = (
            "[AICRAFT_WORLD_CONTEXT]",
            "[AICRAFT_PLANNER_CONTEXT]",
        )
        self.messages[:] = [
            message
            for message in self.messages
            if not (
                message.get("role") == "system"
                and any(
                    message.get("content", "").startswith(marker)
                    for marker in context_markers
                )
            )
        ]


    def _ask_model(self):
        for attempt in range(EMPTY_RESPONSE_RETRIES + 1):
            print(self.messages)

            started = time.monotonic()

            logger.info(
                "MODEL REQUEST START attempt=%d messages=%d",
                attempt + 1,
                len(self.messages),
            )

            try:
                response = self.ollama.chat(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    think=False,
                    options={
                        "num_predict": MAX_OUTPUT_TOKENS,
                        "temperature": 0.2,
                    },
                )

                message = response.message

                content = message.content or ""
                tool_calls = message.tool_calls or []
                thinking = getattr(message, "thinking", "") or ""

                logger.info(
                    "MODEL REQUEST END seconds=%.2f "
                    "tool_calls=%d content_chars=%d thinking_chars=%d",
                    time.monotonic() - started,
                    len(tool_calls),
                    len(content),
                    len(thinking),
                )

                if tool_calls or content.strip():
                    return response

                logger.warning(
                    "Ollama returned an empty response. "
                    "thinking_chars=%d attempt=%d",
                    len(thinking),
                    attempt + 1,
                )

                if attempt < EMPTY_RESPONSE_RETRIES:
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was empty. "
                            "Continue the current task now. "
                            "Call exactly one appropriate tool, "
                            "or briefly explain why the task cannot be completed."
                        ),
                    })
                    continue

                raise RuntimeError(
                    "Ollama returned an empty response after "
                    f"{EMPTY_RESPONSE_RETRIES + 1} attempts"
                )

            except Exception:
                logger.exception(
                    "MODEL REQUEST FAILED seconds=%.2f",
                    time.monotonic() - started,
                )
                raise

    def handle_message(self, message):
        message = message.strip()
        if not message:
            return
        logger.info("Received chat message: %s", message)

        try:
            command_name = shlex.split(message)[0]
        except (IndexError, ValueError):
            command_name = ""

        if command_name in self.player.commandTemplates:
            logger.info("Executing direct command: %s", message)
            self.player.handleChat(message)
            return

        self.remove_last_context() #< MUST be called before appending the new message because it just does pop
        self.additional_context(message)
        self.messages.append({"role": "user", "content": message})

        try:
            logger.info("MODEL START model=%s", self.model)
            response = self._ask_model()

            tool_round = 0
            while response.message.tool_calls:
                tool_round += 1
                if len(response.message.tool_calls) > 1:
                    logger.warning(
                        "MODEL returned %d tool calls; executing only the first and replanning",
                        len(response.message.tool_calls),
                    )
                    response.message.tool_calls = response.message.tool_calls[:1]
                logger.info(
                    "TOOL ROUND %d calls=%d",
                    tool_round,
                    len(response.message.tool_calls),
                )

                self.messages.append(response.message)
                for tool_call in response.message.tool_calls:
                    call_name = tool_call.function.name
                    call_arguments = dict(tool_call.function.arguments)

                    result = self._call_tool(
                        call_name,
                        call_arguments,
                    )
                    self.messages.append({
                        "role": "tool",
                        "tool_name": call_name,
                        "content": json.dumps(result, default=str),
                    })
                    self.messages.append({
                        "role": "user",
                        "content": (
                            f"Command {call_name} finished with result: "
                            f"{json.dumps(result, default=str)}. "
                            "If ok is false, fix the arguments or choose an alternative tool "
                            "before retrying. This command is only one step of the original user request. "
                            "Prompt yourself for the next step and keep using tools until the original "
                            "request is fully satisfied. Do not report completion just because this one "
                            "command finished. Only give a final response when the entire request is done "
                            "or cannot be completed."
                        ),
                    })

                response = self._ask_model()

            self.messages.append(response.message)
            logger.info("MODEL END response=%s", response.message.content)
            self.player.sendMessage(response.message.content)
        except Exception as error:
            logger.exception("Ollama request failed")
            self.player.sendMessage(f"Ollama error: {error}")

if __name__ == "__main__":
    logger.info("Starting AI with Ollama model %s", MODEL)
    try:
        player = Player()
        agent = OllamaAgent(player)
        listener = ChatListener(
            playerName=player.name,
            logFile=os.path.abspath("./logs/latest.log"),
            callback=agent.handle_message,
        )
        listener.start()
        logger.info("Chat listener started for player %s", player.name)
        print(f"AI started with Ollama model: {agent.model}")
        while True:
            time.sleep(1)
    except Exception:
        logger.exception("Fatal startup/runtime error")
        raise
