# GameZip
Designed to be ran by a Torrent client on torrent completion in a linux environment, but can also work standalone

> [!WARNING]
> RAWG API was removed on the last update in favour of IGDB API.
> it requires a 5 step setup involving a Twitch account, read here https://api-docs.igdb.com/#getting-started
> If you would prefer to not use the new API system, stay below version 0.6 of this script.


> [!NOTE]
> Install requirements with 'pip install -r requirements.txt', you also require 7z in your system. Use "apt install p7zip" for Debian systems or p7zip from AUR.

**.env.example must be renamed to .env and configured**, where:

multithread = Set amount of CPU threads for 7z to use during compression

API = Your IGDB API Key

categoryName = Your torrent's games category. Made so the script avoids compressing other stuff from your torrent client that are not games

storeFolder = where the script will store compressed and renamed version of the game

This script will automatically convert messy names to good names, for example, M.i.n_.e.c.raft gets converted to "Minecraft (2011)" and store them in a .7z file


If using Qbittorrent, look for "run external command on torrent finished" and set /usr/bin/python3 main.py -c %L '"%R"' (note there's ' ' and " " combined for files with spaces, I suggest enabling "create subfolders" because without it this script can't directly work with .rar/.zip files)

The parameters are:

-c --category = for the torrent's category
```
python3 main.py -c [CATEGORY] [INPUT]"
```

examples
```bash
python3 main.py -c Games /mnt/gaming/ilikethisgame/

python3 main.py -c Games "/SquareRoot\ Collection\ \[Testing\ Repack\]/"
```

example from my qbittorrent "run on completion" command:

```
/usr/bin/ssh -i /home/qbittorrent-nox/.ssh/id_rsa root@192.168.0.102 python3 /root/GameZip/main.py -c %L '"%R"' 
# It means it executes the script, stored in another more powerful server than my NAS, through ssh
```
### Standalone usage:
Configure a dummy category, for example "A",

then simply execute the script with python3 main.py -c A /mnt/gaming/your/game/

