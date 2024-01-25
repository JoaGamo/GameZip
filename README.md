# GameZip
Designed to be ran by a Torrent client on torrent completion in a linux environment, but can also work standalone
> [!NOTE]
> **Requires 'requests' modules** (for RAWG API), install with "apt install python3-requests". **Also requires 7z package,** install with "apt install p7zip" or p7zip from AUR if using arch.

**.env.example must be renamed to .env and configured**, where:

compressionCMD = set '7zz' if using the apt package, or '7z' if using the previous command.

multithread= Set amount of CPU threads for 7z to use during compression

API = Your RAWG API Key

categoryName = Your torrent's games category. Made so the script avoids unnecesary compressing of non-game torrents, like linux ISOs

storeFolder = the folder the script will store compressed and renamed version of the game

This script will automatically convert messy names to good names, for example, M.i.n_.e.c.raft gets converted to "Minecraft (2011)" and store them in a .7z file


If using Qbittorrent, look for "run external command on torrent finished" and set /usr/bin/python3 main.py -c %L '"%R"' (note there's ' ' and " " combined for files with spaces, I suggest enabling "create subfolders" because without it this script can't directly work with .rar/.zip files)

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

example from my qbittorrent "run on completion" command:

```
/usr/bin/ssh -i /home/qbittorrent-nox/.ssh/id_rsa root@192.168.0.102 python3 /root/GameZip/main.py -c %L '"%R"' # It means it executes the script, stored in another server, through ssh. In the future this command could execute another script to fetch for the least used node and call the script in it.
```

