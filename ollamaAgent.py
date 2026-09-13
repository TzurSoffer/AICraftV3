import logging
import os
import time

from ollama import Client

from minecraft import MinecraftController


logger = logging.getLogger(__name__)


MODEL = "gpt-oss:120b"

OLLAMA_HOST = "http://192.168.0.122:11434"

MAX_OUTPUT_TOKENS = int(
    os.getenv("OLLAMA_MAX_OUTPUT_TOKENS", "256")
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
        self.player = minecraft.player
        self.model = model

        self.ollama = Client(
            host=OLLAMA_HOST,
        )

        self.messages = []

        self.tools = self.minecraft.tools

        self.additionalContext()

    # ==========================================================
    # CONTEXT MANAGEMENT
    # ==========================================================

    def additionalContext(self, currentGoal=None):
        if currentGoal is None:
            currentGoal = (
                self.minecraft.currentGoal
                or "You dont have any current goals."
            )

        try:
            playerSummary = self.player.getPlayerSummary()

        except Exception as error:
            logger.exception(
                "Failed to get player summary"
            )

            playerSummary = (
                f"Unable to read player summary: {error}"
            )

        self.messages.append({
            "role": "system",
            "content": (
                "[AICRAFT_WORLD_CONTEXT]\n"
                "Current player/world information:\n"
                f"{playerSummary}"
            ),
        })

        self.messages.append({
            "role": "system",
            "content": (
                "[AICRAFT_PLANNER_CONTEXT]\n"
                "You are a Minecraft assistant playing on "
                "version 26.2.\n\n"

                "Use the available tools to perform actions "
                "in the world.\n"

                "Never invent tool results.\n"

                "After using tools, briefly explain what "
                "happened.\n"

                "If the tool you need is not available, explain "
                "that you cannot perform the action or use an "
                "alternative tool.\n"

                "When referencing blocks in tools, use the exact "
                "block tag including namespace, for example "
                "minecraft:stone or minecraft:oak_log.\n\n"

                "You are a multi-step planner.\n"

                "If the user asks you to do something requiring "
                "multiple steps, plan out the steps and execute "
                "them one by one.\n"

                "Call exactly one tool per response.\n"

                "Wait for its result before choosing the next "
                "tool.\n\n"

                "IMPORTANT BUILDING RULES:\n"

                "Never place a block at a coordinate that is "
                "already recorded in BUILD MEMORY.\n"

                "Do not repeatedly call the same tool with the "
                "same arguments.\n"

                "Do not claim a structure is finished without "
                "verifying it.\n"

                "A house should have a floor, walls, a door, "
                "and a roof unless the user specifies otherwise.\n"

                "Track your progress using the building plan.\n"

                "If a building plan does not exist, create a "
                "clear plan before building.\n\n"

                f"CURRENT GOAL:\n{currentGoal}\n\n"

                f"{self.minecraft.getBuildingContext()}"
            ),
        })

    def removeLastContext(self):
        contextMarkers = (
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
                    for marker in contextMarkers
                )
            )
        ]

    def trimHistory(self):
        if len(self.messages) <= MAX_HISTORY_MESSAGES:
            return

        systemMessages = [
            message
            for message in self.messages
            if message.get("role") == "system"
        ]

        otherMessages = [
            message
            for message in self.messages
            if message.get("role") != "system"
        ]

        remainingCount = max(
            0,
            MAX_HISTORY_MESSAGES - len(systemMessages),
        )

        self.messages[:] = (
            systemMessages
            + otherMessages[-remainingCount:]
        )

        logger.info(
            "TRIMMED HISTORY messages=%d",
            len(self.messages),
        )

    # ==========================================================
    # MODEL REQUEST
    # ==========================================================

    def askModel(self):
        for attempt in range(
            EMPTY_RESPONSE_RETRIES + 1
        ):
            self.removeLastContext()
            self.additionalContext()
            self.trimHistory()

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

    # ==========================================================
    # CHAT HANDLING
    # ==========================================================

    def handleMessage(self, message):
        message = message.strip()

        if not message:
            return

        logger.info(
            "Received chat message: %s",
            message,
        )

        if self.minecraft.isDirectCommand(message):
            logger.info(
                "Executing direct command: %s",
                message,
            )

            self.minecraft.executeDirectCommand(message)
            return

        self.minecraft.currentGoal = message
        self.minecraft.buildVerified = False
        self.minecraft.currentStep = None

        self.removeLastContext()
        self.additionalContext(message)

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

                if (
                    response.message.content
                    and response.message.content.strip()
                ):
                    self.messages.append(
                        response.message
                    )

                for toolCall in toolCalls:
                    callName = toolCall.function.name

                    callArguments = dict(
                        toolCall.function.arguments
                    )

                    result = self.minecraft.callTool(
                        callName,
                        callArguments,
                    )

                    logger.info(
                        "TOOL RESULT name=%s result=%s",
                        callName,
                        result,
                    )

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

            self.minecraft.sendMessage(
                response.message.content
            )

        except Exception as error:
            logger.exception(
                "Ollama request failed"
            )

            self.minecraft.sendMessage(
                f"Ollama error: {error}"
            )