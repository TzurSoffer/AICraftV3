import json
import logging
import os
import time

from ollama import Client

logger = logging.getLogger(__name__)


# OLLAMA_HOST = "http://192.168.0.122:11434"
OLLAMA_HOST = "http://127.0.0.1:11434"


EMPTY_RESPONSE_RETRIES = int(
    os.getenv("OLLAMA_EMPTY_RESPONSE_RETRIES", "2")
)

class OllamaAgent:

    def __init__(
        self,
        minecraft,
        model="gpt-oss:120b",
        reasoning=True,
    ):
        self.minecraft = minecraft
        self.currentGoal = None
        self.player = minecraft.player
        self.model = model
        self.reasoning = reasoning

        self.ollama = Client(
            host=OLLAMA_HOST,
        )
        
        self.tools = self.minecraft.getTools()
        self.tools.append(
            {
                "type": "function",
                "function": {
                    "name": "FINISHED",
                    "description": "The last tool to call only when the current goal is fully completed.",
                    "parameters": {
                        "type": "object",
                        "required": ["finalMessage"],
                        "properties": {
                            "finalMessage": {"type": "string"}
                        },
                    },
                },
            }
        )
        self.messages = []
        self.run = False

    def additionalContext(self) -> list[dict]:
        playerSummary = self.player.getPlayerSummary()

        context = [
            {
                "role": "system",
                "content": (
                    "[AICRAFT_PLAYER_CONTEXT]\n"
                    f"{playerSummary}"
                ),
            },
            {
                "role": "system",
                "content": (
                    "[AICRAFT_PLANNER_CONTEXT]\n"
                    "You are a Minecraft assistant playing on "
                    "version 26.2.\n\n"

                    "Use the available tools to perform actions "
                    "in the world.\n"

                    "Never invent tool results.\n"

                    "If the tool you need is not available, use an alternative tool.\n"

                    "When referencing blocks in tools, use the exact "
                    "block tag including namespace, for example "
                    "minecraft:stone or minecraft:oak_log.\n\n"

                    "You are a multi-step planner.\n"

                    "If the user asks you to do something requiring "
                    "multiple steps, plan out the steps and execute "
                    "them in order.\n"

                    "You can call the same tool multiple times, but only if it makes logical sense.\n"
                    "eg. if you need to place multiple blocks, you can return multiple place calls in one response.\n"

                    "For repeated placements, mining, or crafting, prefer the batch tools placeBlocks, mineBlocks, and craftItems.\n"
                    "Never abbreviate JSON with ....\n"
                    "For craftItems, provide one itemName and a count. The count means how many times to run the craft operation, not the total number of output items.\n"
                    "Tool arguments must be strict JSON. Never include // comments, /* */ comments, markdown, labels, or trailing commas. Only provide the required arguments.\n"
                    
                    "Batch tool examples:\n"
                    "Valid JSON examples: placeBlocks {\"blockType\": \"minecraft:stone\", \"coordinates\":[{\"x\":10,\"y\":64,\"z\":10},{\"x\":11,\"y\":64,\"z\":10}]}\n"
                    "mineBlocks {\"coordinates\":[{\"x\":10,\"y\":64,\"z\":10},{\"x\":11,\"y\":64,\"z\":10}]}\n"

                    "Batch tool items are executed sequentially in the order provided.\n"

                    "When several actions are already known and do not "
                    "depend on each other's results, return all of their "
                    "tool calls in the same response. The controller will "
                    "execute them sequentially and provide each result.\n"

                    "If a later action depends on an earlier result, "
                    "return only the next required tool call and wait for "
                    "its result.\n"

                    "Do not repeatedly call the same tool with the "
                    "same arguments unless needed (crafting something multiple times).\n"

                    "Never place a block at a coordinate that is "
                    "already recorded in BUILD MEMORY.\n"

                    "Do not claim a structure is finished without "
                    "verifying it.\n"

                    "Track your progress using the building plan.\n"

                    "If a building plan does not exist, create a "
                    "clear plan before building.\n"

                    "If asking to build a 7x7 oak house, first mine 64 oak logs, then craft them into planks, then build the house, make sure to add a chest and door to the interior, nothing else should be inside the house. The house should be 3 blocks high from the inside and have a triangular roof made of planks. The corners should be made of oak logs. add trapdoor windows. Make sure to get 10 percent extra materials so you always have buffer space\n"

                    "After fully completing a step, update the building plan before proceeding to the next step.\n\n"
                ),
            },
            {
                "role": "system",
                "content": (
                    "[AICRAFT_BUILDING_CONTEXT]\n"
                    f"Current building plan:\n{self.minecraft.getBuildingPlan()}"
                ),
            },
        ]
        if self.currentGoal:
            context.append({
                "role": "system",
                "content": (
                    "[AICRAFT_CURRENT_GOAL]\n"
                    f"Current goal:\n{self.currentGoal}"
                ),
            })
        return context

    def askModel(self):
        for attempt in range(
            EMPTY_RESPONSE_RETRIES + 1
        ):
            started = time.monotonic()
            requestMessages = self.messages + self.additionalContext()

            logger.info(
                "MODEL REQUEST START attempt=%d messages=%d",
                attempt + 1,
                len(requestMessages),
            )
            logger.info(
                "MODEL REQUEST HISTORY %s",
                json.dumps(requestMessages, default=str),
            )

            try:
                response = self.ollama.chat(
                    model=self.model,
                    messages=requestMessages,
                    tools=self.tools,
                    think=self.reasoning,
                )

                message = response.message
                content = message.content or ""
                toolCalls = message.tool_calls or []

                thinking = getattr(
                    message,
                    "thinking",
                    "",
                ) or ""

                logger.info(
                    "MODEL REQUEST END seconds=%.2f "
                    "tool_calls=%d content_chars=%d "
                    "thinking_chars=%d",
                    time.monotonic() - started,
                    len(toolCalls),
                    len(content),
                    len(thinking),
                )

                logger.info(
                    "MODEL RESPONSE %s",
                    json.dumps(response.message, default=str),
                )

                if toolCalls or content.strip():
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
                            "or briefly explain why the task "
                            "cannot be completed."
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

    def handleMessage(self, message, setGoal=True):
        message = message.strip()

        if not message:
            return

        if message == "stop":
            self.run = False
            return
        self.run = True

        logger.info(
            "Received chat message: %s",
            message,
        )

        # if self.minecraft.isDirectCommand(message):
        #     logger.info(
        #         "Executing direct command: %s",
        #         message,
        #     )

        #     self.minecraft.executeDirectCommand(message)
        #     return
        
        if setGoal:
            self.currentGoal = message

        self.messages.append({
            "role": "user",
            "content": message,
        })

        try:
            logger.info(
                "MODEL START model=%s",
                self.model,
            )

            response = self.askModel()

            toolRound = 0

            while response.message.tool_calls:
                toolRound += 1

                if toolRound > 500:
                    raise RuntimeError(
                        "Maximum tool rounds exceeded."
                    )

                toolCalls = response.message.tool_calls

                logger.info(
                    "TOOL ROUND %d calls=%d",
                    toolRound,
                    len(toolCalls),
                )

                self.messages.append(response.message)  #< tool response

                for toolCall in toolCalls:
                    callName = toolCall.function.name

                    callArguments = dict(
                        toolCall.function.arguments
                    )

                    logger.info(
                        "TOOL CALL name=%s arguments=%s",
                        callName,
                        callArguments,
                    )
                    
                    if callName == "FINISHED":
                        finalMessage = callArguments.get(
                            "finalMessage",
                            "Task completed.",
                        )

                        logger.info(
                            "TOOL FINISHED finalMessage=%s",
                            finalMessage,
                        )

                        self.minecraft.sendMessage(finalMessage)
                        self.run = False
                        return

                    result = self.minecraft.callTool(
                        callName,
                        callArguments,
                    )

                    logger.info(
                        "TOOL RESULT name=%s result=%s",
                        callName,
                        result,
                    )

                    print("Result:", result)
                    print("-" * 80)

                    self.messages.append({
                        "role": "tool",
                        "tool_name": callName,
                        "content": str(result),
                    })

                response = self.askModel()

            self.messages.append(response.message)

            logger.info(
                "MODEL END response=%s",
                response.message.content,
            )

            logger.info(
                "CONVERSATION HISTORY %s",
                json.dumps(self.messages, default=str),
            )

            if self.run and not response.message.tool_calls:
                self.handleMessage(response.message.content, setGoal=False)

        except Exception as error:
            logger.exception(
                "Ollama request failed"
            )

            self.minecraft.sendMessage(
                f"Ollama error: {error}"
            )