import math
import json
import logging
import os
import time
import threading

import minescript as m


logger = logging.getLogger(__name__)
BARITONE_COMMAND_TIMEOUT = float(os.getenv("BARITONE_COMMAND_TIMEOUT", "120"))


# class ChatListener:
#     def __init__(
#         self,
#         playerName,
#         logFile: str = "../logs/latest.log",
#         callback=None,
#     ):
#         self.run = False
#         self.logFile = logFile

#         self.fileSize = os.path.getsize(self.logFile)     #< quick comparison to avoid converting the file to list of lines if the file hasn't changed
#         self.pendingLines = []
#         self.pendingLinesLock = threading.Lock()
#         self.sendMessagePrefix = f"[Render thread/INFO]: [CHAT] <{playerName}> "
#         self.sendMessagePrefixLength = len(self.sendMessagePrefix)
#         if callback is not None:
#             self.callback = callback
    
#     def start(self):
#         self.run = True
#         threading.Thread(
#             target=self.startListener,
#             name="minecraft-chat-listener",
#             daemon=False,
#         ).start()
    
#     def stop(self):
#         self.run = False
    
#     def callback(self, message):
#         print(message)
    
#     def _getLatestChat(self):
#         fileSize = os.path.getsize(self.logFile)
#         if fileSize == self.fileSize:
#             return None
#         with open(self.logFile, 'r') as f:
#             f.seek(self.fileSize)
#             latest = f.readlines()
#             self.fileSize = fileSize
#             return latest
  
#     def startListener(self):
#         logger.info("Chat listener reading %s", self.logFile)
#         while self.run:
#             try:
#                 time.sleep(0.1) #< needs to be at start cause of "continue" statements below
#                 latest = self._getLatestChat()
#                 if latest:
#                     self.latest = latest
#                     callbacks = []
#                     with self.pendingLinesLock:
#                         for line in latest:
#                             line = re.sub(
#                                 r"^\[\d{2}:\d{2}:\d{2}\]\s*",
#                                 "",
#                                 line.rstrip("\r\n"),
#                                 count=1,
#                             )
#                             if not line:
#                                 continue
#                             self.pendingLines.append(line)
                            
#                             ## Handle callback for chat messages that are sent by the player
#                             if line[:self.sendMessagePrefixLength] != self.sendMessagePrefix:
#                                 continue
#                             line = line[self.sendMessagePrefixLength:]
#                             callbacks.append(line)

#                     for line in callbacks:
#                         logger.info(f"Chat command received: {line}")
#                         self.callback(line)
#             except Exception:
#                 logger.exception("Chat listener failed while reading Minecraft log")

    # def waitForChat(self, prefix, timeout=5, pollInterval=0.1):
    #     beginTime = time.time()
    #     while time.time() - beginTime < timeout:
    #         with self.pendingLinesLock:
    #             unmatched = []
    #             while self.pendingLines:
    #                 latest = self.pendingLines.pop(0)
    #                 if latest[:len(prefix)] != prefix:
    #                     unmatched.append(latest)
    #                     continue
    #                 self.pendingLines[0:0] = unmatched
    #                 return latest[len(prefix) + 1:]
    #             self.pendingLines[0:0] = unmatched

    #         time.sleep(pollInterval)
        # return None

class ChatListener:
    def __init__(
        self,
        playerName,
        logFile: str = "../logs/latest.log",
        callback=None,
    ):
        self.run = False
        self.latest = ""
        self.logFile = logFile
        self.sendMessagePrefix = f"[Render thread/INFO]: [CHAT] <{playerName}> "
        self.sendMessagePrefixLength = len(self.sendMessagePrefix)
        if callback is not None:
            self.callback = callback
    
    def start(self):
        self.run = True
        threading.Thread(
            target=self.startListener,
            name="minecraft-chat-listener",
            daemon=False,
        ).start()
    
    def stop(self):
        self.run = False
    
    def callback(self, message):
        print(message)
    
    def _getLatestChat(self):
        with open(self.logFile, 'r') as f:
            lines = f.readlines()
            if len(lines) > 0:
                return(lines[-1].strip())
            else:
                return(None)

    def waitForChat(self, prefix, timeout=5, pollInterval=0.1):
        beginTime = time.time()
        while time.time() - beginTime < timeout:
            latest = self._getLatestChat()
            if latest != self.latest and len(latest) > 11 and latest[11:][:len(prefix)] == prefix:
                self.latest = latest
                return latest[len(prefix)+12:]
            time.sleep(pollInterval)
        return None
    
    def startListener(self):
        logger.info("Chat listener reading %s", self.logFile)
        while self.run:
            try:
                time.sleep(0.3) #< needs to be at start cause of "continue" statements below
                latest = self._getLatestChat()
                if latest != self.latest:
                    self.latest = latest
                    if len(latest) < 11:
                        continue
                    latest = latest[11:]
                    if latest[:self.sendMessagePrefixLength] != self.sendMessagePrefix:
                        continue
                    latest = latest[self.sendMessagePrefixLength:]
                    logger.info("Chat command received: %s", latest)
                    self.callback(latest)
                    self.latest = latest
            except Exception:
                logger.exception("Chat listener failed while reading Minecraft log")


class Player:
    def __init__(self):
        self.currentSlot = None
        self.running = False

        reName = r"\s*[a-zA-Z0-9_:.-]+\s*"
        self.commandTemplates = {
            "goto": r"\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*",
            "jump": r"",
            "mine": r"\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*",
            "place": (
                r"\s*[a-zA-Z0-9:_-]+\s*,\s*"
                r"-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*"
            ),
            "attack": reName,
            # "findBlock": reName,
            "findStructure": reName,
            "findEntity": reName,
            "craft": reName,
            "rightClick": r"",
            "leftClick": r"",
            "drop": r"",
            "chooseSlot": r"\s*\d+\s*",
            "chat": r".+",
            "lookAt": r"\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*",
            "follow": r"\s*\w+\s*",
            "surroundingEntities": r"",
            "stop": r"",
            "summary": r"",
            "DONE": r"",
        }
        
        self.name = m.player_name()
        self.chat = ChatListener(playerName=self.name, logFile=os.path.abspath("./logs/latest.log"))

    def _player(self):
        return m.player()

    def pos(self):
        return list(self._player().position)

    def _distance(self, a, b):
        return math.sqrt(
            sum((a[i] - b[i]) ** 2 for i in range(3))
        )
    
    def _entityType(self, entity):
        return str(getattr(entity, "type", "unknown")).lower()

    def _entityName(self, entity):
        return str(
            getattr(entity, "name", None)
            or getattr(entity, "type", "unknown")
        )

    def _entityPosition(self, entity):
        return list(entity.position)

    def _normaliseBlockName(self, block):
        block = str(block).lower().strip()

        if not block.startswith("minecraft:"):
            block = f"minecraft:{block}"

        return block

    def _normaliseEntityName(self, entity):
        return str(entity).lower().replace("minecraft:", "")
    
    def _waitForCommand(self, timeout=5, pollInterval=0.1):
        return self.chat.waitForChat("[Render thread/INFO]: [System] [CHAT]", timeout, pollInterval)
    def _waitForBaritone(self, timeout=5, pollInterval=0.1):
        return self.chat.waitForChat("[Render thread/INFO]: [CHAT]", timeout, pollInterval)

    def getInventory(self):
        inventory = {}

        for item in m.player_inventory():
            inventory[item.slot] = {
                "name": item.item,
                "count": item.count,
                "selected": item.selected,
            }

        return inventory

    def getPlayerData(self):
        player = self._player()

        return {
            "pos": [int(p) for p in player.position],
            "inventory": self.getInventory(),
        }

    def getHealth(self):
        player = self._player()

        return getattr(
            player,
            "health",
            getattr(player, "hp", None),
        )

    def getHunger(self):
        player = self._player()

        return getattr(
            player,
            "hunger",
            getattr(player, "food", None),
        )

    def getBiome(self):
        player = self._player()

        # MineScript versions may expose biome as a property.
        biome = getattr(player, "biome", None)

        if biome is not None:
            return str(biome)

        return "unknown"

    def getBlock(self, x, y, z):
        return m.getblock(int(x), int(y), int(z))

    def surroundingBlocks(self, radius=5, radiusY=2):
        blocks = []

        px, py, pz = [int(coord) for coord in self.pos()]

        for dx in range(-radius, radius + 1):
            for dy in range(-radiusY, radiusY + 1):
                for dz in range(-radius, radius + 1):
                    x = px + dx
                    y = py + dy
                    z = pz + dz

                    block = self.getBlock(x, y, z)

                    if block == "minecraft:air":
                        continue

                    blocks.append({
                        "block": block,
                        "pos": [x, y, z],
                    })

        return blocks

    # def findBlock(self, blockType, radius=32, radiusY=16):
    #     """
    #     Find all matching blocks in a cuboid around the player.

    #     Example:
    #         findBlock("diamond_ore")
    #     """

    #     blockType = self._normaliseBlockName(blockType)

    #     px, py, pz = [int(coord) for coord in self.pos()]
    #     blocks = []

    #     for dx in range(-radius, radius + 1):
    #         for dy in range(-radiusY, radiusY + 1):
    #             for dz in range(-radius, radius + 1):
    #                 x = px + dx
    #                 y = py + dy
    #                 z = pz + dz

    #                 if self.getBlock(x, y, z) != blockType:
    #                     continue

    #                 distance = math.sqrt(dx**2 + dy**2 + dz**2)

    #                 blocks.append({
    #                     "block": blockType,
    #                     "pos": [x, y, z],
    #                     "distance": round(distance, 2),
    #                 })

    #     blocks.sort(key=lambda block: block["distance"])

    #     return blocks

    # def findNearestBlock(self, blockType, radius=32, radiusY=16):
    #     blocks = self.findBlock(blockType, radius, radiusY)

    #     if not blocks:
    #         return None

    #     return blocks[0]

    def mine(self, x, y, z):
        m.chat("#allowBreak true")
        m.chat("#sel clear")
        m.chat(f"#sel pos1 {int(x)} {int(y)} {int(z)}")
        m.chat(f"#sel pos2 {int(x)} {int(y)} {int(z)}")
        m.chat(f"#sel fill air")
        deadline = time.time() + BARITONE_COMMAND_TIMEOUT
        while time.time() < deadline:
            response = self._waitForBaritone()
            if response == "[Baritone] Done building":
                return "Mined block successfully."
        return f"Mining timed out after {BARITONE_COMMAND_TIMEOUT:g} seconds."
    
    def mineBlock(self, total, blockName):
        """
        Mine the requested block until the player has the requested amount in their inventory.

        Example:
            mineBlock(5, "minecraft:diamond_ore")
        """
        m.chat("#allowBreak true")
        m.chat(f"#mine {total} {blockName}")
        deadline = time.time() + BARITONE_COMMAND_TIMEOUT
        while time.time() < deadline:
            response = self._waitForBaritone()
            if type(response) == str and response.startswith("[Baritone] Have "):
                print(f"Have {total} {blockName} in inventory.")
                return "Mined blocks successfully."
        return f"Mining timed out after {BARITONE_COMMAND_TIMEOUT:g} seconds."

    def surroundingEntities(self):
        entities = []

        for entity in m.entities():
            entities.append({
                "type": self._entityType(entity),
                "name": self._entityName(entity),
                "pos": [
                    int(coord)
                    for coord in self._entityPosition(entity)
                ],
            })

        return entities

    def findEntities(self, entityType=None, radius=32):
        """
        Find entities around the player.

        entityType:
            None -> all entities
            "zombie" -> zombies
            "minecraft:zombie" -> zombies
        """

        playerPos = self.pos()
        entities = []

        if entityType is not None:
            entityType = self._normaliseEntityName(entityType)

        for entity in m.entities():
            entityPos = self._entityPosition(entity)

            distance = self._distance(playerPos, entityPos)

            if distance > radius:
                continue

            currentType = self._entityType(entity)
            currentName = self._normaliseEntityName(
                self._entityName(entity)
            )

            if entityType is not None:
                if (
                    entityType != currentType
                    and entityType != currentName
                ):
                    continue

            entities.append({
                "type": currentType,
                "name": self._entityName(entity),
                "pos": [
                    round(coord, 2)
                    for coord in entityPos
                ],
                "distance": round(distance, 2),
            })

        entities.sort(key=lambda entity: entity["distance"])

        return entities

    def _isMonster(self, entity):
        """
        Common hostile mobs.

        This list can be expanded for modded mobs.
        """

        monsterTypes = {
            "minecraft:zombie",
            "minecraft:skeleton",
            "minecraft:creeper",
            "minecraft:spider",
            "minecraft:cave_spider",
            "minecraft:enderman",
            "minecraft:witch",
            "minecraft:slime",
            "minecraft:magma_cube",
            "minecraft:phantom",
            "minecraft:drowned",
            "minecraft:husk",
            "minecraft:stray",
            "minecraft:blaze",
            "minecraft:ghast",
            "minecraft:pillager",
            "minecraft:vindicator",
            "minecraft:evoker",
            "minecraft:ravager",
            "minecraft:warden",
            "minecraft:hoglin",
            "minecraft:zoglin",
            "minecraft:piglin_brute",
            "minecraft:guardian",
            "minecraft:elder_guardian",
            "minecraft:silverfish",
            "minecraft:endermite",
            "minecraft:shulker",
            "minecraft:phantom",
            "minecraft:breeze",
        }

        entityType = self._entityType(entity)

        return entityType in monsterTypes

    def findNearbyMonsters(
        self,
        xRadius=15,
        yRadius=15,
        zRadius=3,
    ):
        """
        Find monsters in the requested area.

        X: +/- 15 blocks
        Y: +/- 15 blocks
        Z: +/- 3 blocks

        Includes distance and exact coordinates.
        """

        playerPos = self.pos()
        monsters = []

        for entity in m.entities():
            if not self._isMonster(entity):
                continue

            entityPos = self._entityPosition(entity)

            dx = entityPos[0] - playerPos[0]
            dy = entityPos[1] - playerPos[1]
            dz = entityPos[2] - playerPos[2]

            if abs(dx) > xRadius:
                continue

            if abs(dy) > yRadius:
                continue

            if abs(dz) > zRadius:
                continue

            distance = self._distance(playerPos, entityPos)

            monsters.append({
                "type": self._entityType(entity),
                "name": self._entityName(entity),
                "distance": round(distance, 2),
                "coords": [
                    round(entityPos[0], 2),
                    round(entityPos[1], 2),
                    round(entityPos[2], 2),
                ],
                "delta": [
                    round(dx, 2),
                    round(dy, 2),
                    round(dz, 2),
                ],
            })

        monsters.sort(key=lambda entity: entity["distance"])

        return monsters

    def attack(self, entityType=None, radius=4.5):
        """
        Attack the nearest matching entity.

        This selects the nearest matching entity and aims
        at it before attacking.

        Example:
            attack("zombie")
            attack()
        """

        entities = self.findEntities(entityType, radius)

        if not entities:
            self.sendMessage("No matching entity nearby.")
            return None

        target = entities[0]

        x, y, z = target["pos"]

        self.lookAt(x, y, z)
        self.leftClick()

        return target

    def attackNearestMonster(self, radius=4.5):
        monsters = self.findNearbyMonsters(
            xRadius=radius,
            yRadius=radius,
            zRadius=radius,
        )

        if not monsters:
            self.sendMessage("No monster nearby.")
            return None

        target = monsters[0]

        x, y, z = target["coords"]

        self.lookAt(x, y, z)
        self.leftClick()

        return target

    def goto(self, x, y, z):
        m.chat(f"#goto {int(x)} {int(y)} {int(z)}")

    def stop(self):
        m.chat("#stop")

    def follow(self, playerName):
        m.chat(f"#follow {playerName}")

    def jump(self):
        m.player_press_jump(True)
        time.sleep(0.1)
        m.player_press_jump(False)

    def leftClick(self):
        m.player_press_attack(True)
        time.sleep(0.1)
        m.player_press_attack(False)

    def rightClick(self):
        m.player_press_use(True)
        time.sleep(0.1)
        m.player_press_use(False)

    def drop(self):
        m.player_press_drop(True)
        time.sleep(0.1)
        m.player_press_drop(False)
    
    def craftItems(self, itemName, amount):
        m.execute(f"/craftItems {itemName} {int(amount)}")
        return self._waitForCommand()

    def chooseSlot(self, slot):
        m.player_inventory_select_slot(int(slot))

    def place(self, blockType, x, y, z):
        blockType = self._normaliseBlockName(blockType)

        m.chat("#allowBreak false")
        m.chat("#sel clear")
        m.chat(f"#sel pos1 {int(x)} {int(y)} {int(z)}")
        m.chat(f"#sel pos2 {int(x)} {int(y)} {int(z)}")
        m.chat(f"#sel fill {blockType}")
        deadline = time.time() + 10
        while time.time() < deadline:
            response = self._waitForBaritone()
            if response == None:
                continue
            if response == "[Baritone] Done building":
                return "Placed block successfully."
            if response.startswith("[Baritone] Unable to do it"):
                return "Missing block in inventory. Could not place block."
        return f"Placement timed out after {10:g} seconds."

    def sendMessage(self, message):
        if isinstance(message, (dict, list)):
            message = json.dumps(message, default=str)

        m.echo(str(message))

    def lookAt(self, x, y, z):
        """
        Look at the center of a block or entity position.
        """

        player = self._player()

        px, py, pz = player.position

        eyeX = px
        eyeY = py + 1.62
        eyeZ = pz

        targetX = x + 0.5
        targetY = y + 0.5
        targetZ = z + 0.5

        dx = targetX - eyeX
        dy = targetY - eyeY
        dz = targetZ - eyeZ

        horizontalDistance = math.sqrt(dx**2 + dz**2)

        if horizontalDistance == 0:
            horizontalDistance = 0.0001

        yaw = math.degrees(math.atan2(-dx, dz)) % 360
        pitch = -math.degrees(
            math.atan2(dy, horizontalDistance)
        )

        m.player_set_orientation(yaw, pitch)

    def findStructure(self, structureType):
        """ return the nearest structure of the given type. """
        m.execute("/locate structure " + structureType)
        response = self._waitForCommand()
        if "[" in response:
            coordinates = f"{structureType} found at: ({response[response.find('[')+1:response.find(']')]})"
            return coordinates
        return f"No {structureType} found."

    def getPlayerSummary(self):
        """
        Return a detailed summary of the player.

        Includes:
            - Position
            - Biome
            - Health
            - Hunger
            - Inventory
            # - Nearby monsters
        """

        player = self._player()

        position = [
            round(coord, 2)
            for coord in player.position
        ]

        summary = {
            "player": {
                "position": position,
                "x": position[0],
                "y": position[1],
                "z": position[2],
                "biome": self.getBiome(),
                "health": self.getHealth(),
                "hunger": self.getHunger(),
            },

            "nearbyMonsters": self.findNearbyMonsters(
                xRadius=15,
                yRadius=15,
                zRadius=3,
            ),

            "inventory": self.getInventory(),
            
            # "surroundingEntities": self.surroundingEntities(),
        }

        return summary

    def handler(self, commands):
        validResult = []

        for i, command in enumerate(commands):
            commandName = command["cmd"]
            args = command.get("args", [])

            try:
                if commandName == "goto":
                    self.goto(*args)

                elif commandName == "mine":
                    self.mine(*args)
                
                elif commandName == "mineBlock":
                    self.mineBlock(*args)
                
                elif commandName == "craftItems":
                    self.craftItems(*args)

                elif commandName == "place":
                    self.place(*args)

                elif commandName == "jump":
                    self.jump()

                elif commandName == "leftClick":
                    self.leftClick()

                elif commandName == "rightClick":
                    self.rightClick()

                elif commandName == "drop":
                    self.drop()

                elif commandName == "chooseSlot":
                    self.chooseSlot(*args)

                elif commandName == "chat":
                    self.sendMessage(*args)

                elif commandName == "attack":
                    self.attack(*args)

                elif commandName == "attackNearestMonster":
                    self.attackNearestMonster(*args)

                # elif commandName == "findBlock":
                #     result = self.findBlock(*args)
                #     self.sendMessage(result)

                # elif commandName == "findNearestBlock":
                #     result = self.findNearestBlock(*args)
                #     self.sendMessage(result)

                elif commandName == "findEntity":
                    result = self.findEntities(*args)
                    self.sendMessage(result)

                elif commandName == "surroundingEntities":
                    result = self.surroundingEntities()
                    self.sendMessage(result)
                
                elif commandName == "findStructure":
                    result = self.findStructure(*args)
                    self.sendMessage(result)

                elif commandName == "findMonsters":
                    result = self.findNearbyMonsters(*args)
                    self.sendMessage(result)

                elif commandName == "summary":
                    result = self.getPlayerSummary()
                    self.sendMessage(result)

                elif commandName == "getInventory":
                    result = self.getInventory()
                    self.sendMessage(result)

                elif commandName == "getBlock":
                    result = self.getBlock(*args)
                    self.sendMessage(result)

                elif commandName == "follow":
                    self.follow(*args)

                elif commandName == "stop":
                    self.stop()

                elif commandName == "lookAt":
                    self.lookAt(*args)

                elif commandName == "DONE":
                    self.sendMessage("DONE!")

                else:
                    print(f"Unknown command: {commandName}")
                    continue

                validResult.append(i)

            except Exception as error:
                print(
                    f"Error executing command "
                    f"{commandName}: {error}"
                )

        return validResult

    def handleChat(self, message):
        """Parse one chat message and execute it as a player command."""

        message = message.strip()
        if not message:
            return

        try:
            parts = message.split(" ")
        except ValueError as error:
            self.sendMessage(f"Invalid command: {error}")
            return

        commandName = parts[0]

        if commandName == "chat":
            args = [message[len(commandName):].strip()]
        else:
            args = []
            for part in parts[1:]:
                args.extend(value for value in part.split(",") if value)

        self.handler([{"cmd": commandName, "args": args}])

if __name__ == "__main__":
    cl = ChatListener(playerName="NotALinuxUser", logFile=os.path.abspath("./logs/latest.log"))
    cl.waitForChat("NotALinuxUser", timeout=5, pollInterval=0.1)
    # import os
    # player = Player()

    # listener = ChatListener(
    #     # playerName=player.name,
    #     playerName="NotALinuxUser",
    #     logFile=os.path.abspath("./logs/latest.log"),
    #     callback=player.handleChat,
    # )
    # listener.start()
    # print("AI started")
    # while True:
    #     time.sleep(1)