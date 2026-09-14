import logging
import os
import time

from minecraft import MinecraftController
from ollamaAgent import OllamaAgent


MODEL = "gpt-oss:120b"

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