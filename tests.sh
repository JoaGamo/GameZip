#!/bin/bash

mkdir -p "testing2/It Takes Two [Zombie Repack]"
mkdir "testing2/Elder Scrolls V Skyrim [Zombie Repack]"
mkdir "testing2/The Witcher 3 Wild Hunt [Zombie Repack]"
mkdir "testing2/Hades [Zombie Repack]"
mkdir "testing2/PEAK [Skeleton Repack]"
mkdir "testing2/Portal [Creeper Repack]"

# Activate venv and install dependencies, then run CLI commands
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/It Takes Two [Zombie Repack]"
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/Elder Scrolls V Skyrim [Zombie Repack]"
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/The Witcher 3 Wild Hunt [Zombie Repack]"
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/Hades [Zombie Repack]"
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/PEAK [Skeleton Repack]"
.venv/bin/python game_processor_refactored.py -c Juegos "testing2/Portal [Creeper Repack]"
