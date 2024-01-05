# GameZip
Automatically zip files in source folder to target folder, auto-corrects the game's name and adds the release date to it.

Designed to be ran in the background as a service in a linux environment

Requires 'watchdog' and 'requests' modules, install with "pip install watchdog requests"

Must be configured inside the file, where:
API = Your RAWG API Key
watchFolder = the folder the script will watch for game's folders
storeFolder = the folder the script will store compressed and renamed versions of the folders in watchFolder

This script will automatically convert messy names to good names, for example, M.i.n_.e.c.raft gets converted to "Minecraft (2011)" and store them in a .zip file, guided by doCompression if you wanted it compressed or not.

You can choose to use compression (Zip Deflated) or disable (0% compression) by changing doCompression variable (Default: True)

Known problems and bugs: 

1) If the script was executed after there were folders in watchFolder, the script won't read them. Solution is moving (not copy, move with "mv") folders to another temporal folder outside of it, then moving them back. My skills aren't good enough to solve this



Made in python 3.11 with 35% of help from AI and my experience from java, this is my first Python script.
