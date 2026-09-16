# AICraftV3

AICraftV3 is a Minecraft assistant that connects an Ollama model to Minecraft through MineScript and Baritone. The model receives world context, chooses tools, and executes actions such as movement, mining, placement, crafting, combat, and building-plan updates.

[![AI plays Minecraft](https://img.youtube.com/vi/IdQpcH2k9_Y/0.jpg)](https://www.youtube.com/shorts/IdQpcH2k9_Y)

## Architecture

```text
Minecraft + MineScript
	v
MCBridge.py / MinecraftController
	v
OllamaAgent.py ---- Ollama HTTP API
	v
aicraft.log
```

- [`main.py`](main.py) starts the controller, agent, logging, and chat listener.
- [`ollamaAgent.py`](ollamaAgent.py) sends context and tool definitions to Ollama and executes returned tool calls.
- [`minecraft.py`](minecraft.py) exposes Minecraft tools and maintains building memory.
- [`MCBridge.py`](MCBridge.py) connects Python actions to MineScript and waits for Minecraft or Baritone responses.
- [`craft mod`](craft%20mod) contains the Fabric mod used for the custom crafting command.

## Requirements

- Python 3.10 or newer.
- Minecraft with the required Fabric, MineScript, craftmod, and Baritone setup.
- Ollama running locally or on a reachable machine.
- The Python dependency in [`requirements.txt`](requirements.txt).
- Java and Gradle if rebuilding the Fabric mod.

## Installation for multi-mc
- Create a multi-mc instance on version 26.2
- Install fabric into the instance
- Install [baritone](https://github.com/cabaletta/baritone/releases/tag/v1.19.0), [minescript](https://modrinth.com/mod/minescript/version/5.0b11-fabric-26.2), and my [/craft](https://github.com/TzurSoffer/AICraftV3/releases/tag/CRAFTMODV1.0.0) mod

- Open your instance and start a new world (to create the minescript folder)
- Close minecraft

Install the Python dependency into the minescript:
`pip install numpy --target "system/lib"` (run in your minescript folder)

copy the files from here into the minescript folder

## Ollama configuration

The current defaults are defined in [`main.py`](main.py) and [`ollamaAgent.py`](ollamaAgent.py). Environment variables are recommended for changing them without editing source:

```powershell
$env:OLLAMA_HOST="http://127.0.0.1:11434"
$env:OLLAMA_MODEL="gemma4:31b"
```
## Run the assistant

From a minecraft world type `\main` into the chat. Now any message you send will be done. If you want an external player to controll the account, change that in the main.py file in the minescript folder or change the `MINECRAFT_PLAYER_NAME` env variable to the name.
The assistant listens for chat from the configured player and sends model responses back into Minecraft. Logs are written to [`aicraft.log`](aicraft.log).

## Build the crafting mod

Run Gradle from the mod directory:

```powershell
Push-Location ".\craft mod"
.\gradlew.bat build
Pop-Location
```

The built mod artifact is produced under `craft mod\build\libs`.

## Troubleshooting

### Ollama connection errors

Check that Ollama is running, the configured host is correct, port `11434` is open, and the model exists on that host.

### Invalid tool-call JSON

Errors mentioning `invalid character '/'` or `invalid character '.'` mean the model emitted comments or `...` inside a tool argument. Increase the model's output capacity or split the operation into smaller batch calls. Tool arguments must be complete JSON before Ollama can parse them.

### Long pauses during actions

Minecraft and Baritone actions are synchronous and wait for chat output from the game. Inspect [`aicraft.log`](aicraft.log) for the last `TOOL START`, `TOOL END`, or listener message to identify the blocked operation.
