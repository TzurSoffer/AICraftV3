import logging
import os
import time

from minecraft import MinecraftController
from ollamaAgent import OllamaAgent


MODEL = "gemma4:31b-cloud"
REASONING=True #< use "medium" for gpt-oss:120b, True for gemma4:31b-cloud

LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "aicraft.log",
)


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    encoding="utf-8",
    force=True,
)

logger = logging.getLogger(__name__)


def main():
    logger.info(
        "Starting AI with Ollama model %s",
        MODEL,
    )

    minecraft = MinecraftController()

    agent = OllamaAgent(
        minecraft=minecraft,
        model=MODEL,
        reasoning=REASONING
    )

    minecraft.startChatListener(
        callback=agent.handleMessage,
        controlledByPlayerName="NotALinuxUser"
    )

    print(
        f"AI started with Ollama model: {agent.model}"
    )

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()

    except Exception:
        logger.exception(
            "Fatal startup/runtime error"
        )

        raise