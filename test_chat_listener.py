import sys
import tempfile
import threading
import time
from pathlib import Path
from types import ModuleType


# MCBridge imports minescript, which is only available inside Minecraft.
minescript_stub = ModuleType("minescript")
minescript_stub.player_name = lambda: "TestPlayer"
sys.modules.setdefault("minescript", minescript_stub)

from MCBridge import ChatListener


TIMESTAMP = "[21:00:00] "


def append_log(path, line):
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(TIMESTAMP + line + "\n")


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for simulated listener activity")


def main():
    with tempfile.TemporaryDirectory() as directory:
        log_path = Path(directory) / "latest.log"
        log_path.write_text("", encoding="utf-8")

        received_chat = []
        listener = ChatListener(
            playerName="TestPlayer",
            logFile=str(log_path),
            callback=received_chat.append,
        )

        listener.run = True
        listener_thread = threading.Thread(
            target=listener.startListener,
            name="test-chat-listener",
        )
        listener_thread.start()

        try:
            append_log(
                log_path,
                "[Render thread/INFO]: [CHAT] <TestPlayer> build a house",
            )
            wait_until(lambda: received_chat == ["build a house"])

            append_log(
                log_path,
                "[Render thread/INFO]: [CHAT] [Baritone] Done building",
            )
            append_log(
                log_path,
                "[Render thread/INFO]: [System] [CHAT] Crafting complete",
            )



            baritone_result = listener.waitForChat(
                "[Render thread/INFO]: [CHAT]",
                timeout=3,
                pollInterval=0.02,
            )
            assert baritone_result == "[Baritone] Done building", baritone_result

            system_result = listener.waitForChat(
                "[Render thread/INFO]: [System] [CHAT]",
                timeout=3,
                pollInterval=0.02,
            )
            assert system_result == "Crafting complete", system_result

            print("PASS: player chat callback and Baritone/system responses work")
        finally:
            listener.stop()
            listener_thread.join(timeout=3)
            if listener_thread.is_alive():
                raise AssertionError("Listener thread did not stop")


if __name__ == "__main__":
    main()
