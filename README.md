# Torrent GameZip
Designed to be ran by a Torrent client on torrent completion in a linux environment
> [!NOTE]
> **Requires 'requests' modules** (for RAWG API), install with "apt install python3-requests". **Also requires 7z package,** install with "apt install p7zip" or p7zip from AUR if using arch.

**Must be configured inside the main.py file**, where:

compressionCMD = set '7zz' if using the apt package, or '7z' if using the previous command.

multithread= Set amount of CPU threads for 7z to use during compression

API = Your RAWG API Key

categoryName = Your torrent's games category. Made so the script avoids unnecesary compressing of non-game torrents, like linux ISOs

storeFolder = the folder the script will store compressed and renamed version of the game

This script will automatically convert messy names to good names, for example, M.i.n_.e.c.raft gets converted to "Minecraft (2011)" and store them in a .7z file


If using Qbittorrent, look for "run external command on torrent finished" and set /usr/bin/python3 main.py -c %L '"%F"' (note there's ' ' and " " combined for files with spaces)

The parameters are:

-c --category = for the torrent's category
```
python3 main.py -c [CATEGORY] [INPUT"
```

examples
```bash
python3 main.py -c Juegos /mnt/gaming/ilikethisgame/

python3 main.py -c Juegos "/SquareRoot\ Collection\ \[Testing\ Repack\]/"
```

Made in python 3.11 with 20% of help from AI and my experience from java, this is my first Python script
