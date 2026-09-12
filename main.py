import json
from collections import deque
import re
from ollama import chat, ChatResponse


def add(a: int, b: int) -> int:
  """Add two numbers"""
  """
  Args:
    a: The first number
    b: The second number

  Returns:
    The sum of the two numbers
  """
  return a + b


def multiply(a: int, b: int) -> int:
  """Multiply two numbers"""
  """
  Args:
    a: The first number
    b: The second number

  Returns:
    The product of the two numbers
  """
  return a * b


available_functions = {
  'add': add,
  'multiply': multiply,
}

messages = [{'role': 'user', 'content': 'What is (11434+12341)*412?'}]
while True:
    response: ChatResponse = chat(
        model='qwen3',
        messages=messages,
        tools=[add, multiply],
        think=True,
    )
    messages.append(response.message)
    print("Thinking: ", response.message.thinking)
    print("Content: ", response.message.content)
    if response.message.tool_calls:
        for tc in response.message.tool_calls:
            if tc.function.name in available_functions:
                print(f"Calling {tc.function.name} with arguments {tc.function.arguments}")
                result = available_functions[tc.function.name](**tc.function.arguments)
                print(f"Result: {result}")
                # add the tool result to the messages
                messages.append({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
    else:
        # end the loop when there are no more tool calls
        break
  # continue the loop with the updated messages



# playerData = {
#     "position": m.player_get_position(),
#     "orientation": m.player_get_orientation(),
#     "targetedBlock": m.player_get_targeted_block(),
#     "inventory": m.player_get_inventory(),
#     "selectedSlot": m.player_get_selected_slot(),
# }}

class Brain:
    def __init__(self, commandSchema: dict, model: str ="gpt-4o", callback=print):
        self.model = model
        self.schema = commandSchema
        # self.schema["DONE"] = ""
        self.callback = callback
        self.history = deque(maxlen=200)
    
    def process(self, context: str, blockData: dict, entityData: dict, playerData: dict) -> dict:

        messages = [
            {"role": "system", "content": (
                "You are a simple Minecraft client. Choose one or more actions from the available options based on the input.\n"+ #<  Once your task is complete, select the DONE option.
                "Each action must be formatted as:\n"+
                "command *args #explanation\n"+
                "If multiple actions are needed, list them in order of execution, each on a separate line.\n"
            )},

            {"role": "user", "content": 
                f"Here are your available options: {json.dumps(self.schema)}\n"
                f"Blocks around you: {json.dumps(blockData)}\n"
                f"Entities around you: {json.dumps(entityData)}\n"
                f"Player data: {json.dumps(playerData)}\n"
                f"Last commands: {json.dumps(list(self.history))}\n"
                f"Context: {context}"
            }
        ]

        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
        )
        print(response)
        # print(json.dumps(entityData))

        actions, raws = self._chooseActionsBasedOnResponse(response)
        
        validResults = self.callback(actions)
        if type(validResults) == list:
            for validResult in validResults:
                self.history.append(raws[validResult])

        return(actions)
    
    def _chooseActionsBasedOnResponse(self, response):
        actions = []
        raws = []
        for cmd, pattern in self.schema.items():
            if pattern:
                # Match cmd followed by args like -12,34,-5
                regex = rf"\b{cmd}\s+({pattern})"
                found = re.findall(regex, response)
                for match in found:
                    args = match.split(',')  # Convert "x,y,z" to list
                    actions.append({"cmd": cmd, "args": args})
                    raw = f"{cmd} "+",".join(args)
                    raws.append(raw)
            else:
                # Match command without args
                regex = rf"\b{cmd}\b"
                if re.search(regex, response):
                    actions.append({"cmd": cmd, "args": []})
        return(actions, raws)


if __name__ == "__main__":
    schema = {
        "goto": r"-?\d+,-?\d+,-?\d+",
        "jump": r"",
        "mine": r"-?\d+,-?\d+,-?\d+",
        "left-click": r"",
        "right-click": r"",
        "drop": r"",
        "chooseSlot": r"\d+",
        "chat": r"\w",
    }

    brain = Brain(schema)
    print(brain.process("mine the orange wool", {"orange_wool": [40, 2, 6], "grass": [0,0,0]}, {"pos": [0,0,0]}))
