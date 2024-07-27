# GameZip
GameZip is designed to be run by a torrent client upon torrent completion in a Linux environment but can also function as a standalone application.

> [!IMPORTANT]
> In the latest update, IGDB support has been added as an alternative to RAWG. 
> Using IGDB requires a 5-step setup involving a Twitch account. For more details, read [here](https://api-docs.igdb.com/#getting-started).
> If you prefer to use IGDB, leave the "API=" field empty

> [!NOTE]
> Install the required packages using `pip install -r requirements.txt`. 
> Additionally, 7z is required on your system. For Debian systems, use `apt install p7zip`, or install p7zip from the AUR on Arch-based systems.

### Configuration
1. **Rename** `.env.example` to `.env` and configure the following fields:

    - `multithread`: Set the number of CPU threads for 7z to use during compression.
    - `API`: Your RAWG API Key.
    - `categoryName`: The category name for your torrent's games. This ensures the script only compresses game files and not other types of files.
    - `storeFolder`: The directory where the script will store the compressed and renamed versions of the games.

This script will automatically clean up and standardize game names. For example, "M.i.n_.e.c.raft" will be converted to "Minecraft (2011)" and stored in a .7z file.

### Qbittorrent Integration
To configure Qbittorrent, go to "Run external command on torrent finished" and set the command to:
```
/usr/bin/python3 main.py -c %L '"%R"'
```
Note the use of both single (' ') and double (" ") quotes to handle files with spaces. It is recommended to enable the "create subfolders" option, as the script cannot directly process .rar/.zip files without it.

### Script Parameters
- `-c` or `--category`: Specifies the torrent's category.
```
python3 main.py -c [CATEGORY] [INPUT]
```

#### Examples
```bash
python3 main.py -c Games /mnt/gaming/ilikethisgame/

python3 main.py -c Games "/SquareRoot\ Collection\ \[Testing\ Repack\]/"
```

#### Example Qbittorrent "Run on Completion" Command
```bash
/usr/bin/ssh -i /home/qbittorrent-nox/.ssh/id_rsa root@192.168.0.11 python3 /root/GameZip/main.py -c %L '"%R"'
```
This command, which is the one I use myself, executes the script on a more powerful server via SSH, rather than on the NAS.

### Standalone Usage
1. Configure a dummy category, for example, "A".
2. Execute the script:
```bash
python3 main.py -c A /mnt/gaming/your/game/
```
