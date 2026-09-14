import json
import logging
import os
import time

from ollama import Client

logger = logging.getLogger(__name__)


MODEL = "gpt-oss:120b"

OLLAMA_HOST = "http://192.168.0.122:11434"

MAX_OUTPUT_TOKENS = int(
    os.getenv("OLLAMA_MAX_OUTPUT_TOKENS", "1024")
)

EMPTY_RESPONSE_RETRIES = int(
    os.getenv("OLLAMA_EMPTY_RESPONSE_RETRIES", "2")
)

MAX_HISTORY_MESSAGES = int(
    os.getenv("OLLAMA_MAX_HISTORY_MESSAGES", "80")
)


class OllamaAgent:

    def __init__(
        self,
        minecraft,
        model=MODEL,
    ):
        self.minecraft = minecraft
        self.currentGoal = None
        self.player = minecraft.player
        self.model = model

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
                    "them one by one.\n"

                    "Call exactly one tool per response.\n"

                    "Do not repeatedly call the same tool with the "
                    "same arguments.\n"

                    "Never place a block at a coordinate that is "
                    "already recorded in BUILD MEMORY.\n"

                    "Do not claim a structure is finished without "
                    "verifying it.\n"

                    "Track your progress using the building plan.\n"

                    "If a building plan does not exist, create a "
                    "clear plan before building.\n"
                    
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
                    think="low",
                    options={
                        "num_predict": MAX_OUTPUT_TOKENS,
                        # "temperature": 0.2,
                    },
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

                if len(toolCalls) > 1:
                    logger.warning(
                        "MODEL returned %d tool calls; "
                        "executing only the first",
                        len(toolCalls),
                    )

                    toolCalls = toolCalls[:1]

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

                        self.minecraft.sendMessage(response.message.content)
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