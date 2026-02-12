from src.actuators import Actuator, ManualButton, load_config

# Initializing hardware from config
config = load_config("config.json")

# Create dictionaries to store instances
actuators = {}
for item in config["actuators"]:
    actuators[item["id"]] = Actuator(item["pin"], item["id"])

buttons = []
for item in config["buttons"]:
    btn = ManualButton(item["pin"], item["id"], item["target"])
    buttons.append(btn)

# Main loop logic
while True:
    for btn in buttons:
        if btn.is_pressed():
            # Control the linked actuator defined in config
            target = actuators.get(btn.target_id)
            if target:
                target.toggle()
