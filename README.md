# GameZip

GameZip is a Python script that processes a target directory based on the specified category.

- **If it's a "Game"**: The script will use the RAWG or IGDB API to correct the file name, compress the game, and store it in the directory specified in the `.env` configuration file.
- **If it's not a game**: The script will create a hard link to the target file in the directory specified in the configuration file.

GameZip is designed to be triggered by a torrent client upon torrent completion in a Linux environment but can also be executed as a standalone script.

# Configuration
> [!NOTE]
> Install the required packages using `pip install -r requirements.txt`. 
> Additionally, 7z (for handling file compression) is required on your system. For Debian systems, use `apt install p7zip`. Also make sure you have unrar installed if you are dealing with RAR files. Do `apt install unrar-free` for it.

> [!IMPORTANT]
> In the latest update, IGDB support has been added as an alternative to RAWG. 
> Using IGDB requires a 5-step setup involving a Twitch account. For more details, read [here](https://api-docs.igdb.com/#getting-started).
> If you prefer to use IGDB, leave the API= field empty; for RAWG, fill it with your API key.

1. **Rename** `.env.example` to `.env` and configure the following fields:

    - `multithread`: Set the number of CPU threads for 7z to use during compression.
    - `API`: Your RAWG API Key.
    - `categoryName`: The category name for your torrent's games. This ensures the script only compresses game files and not other types of files.
    - `storeFolder`: The directory where the script will store the compressed and renamed versions of the games.

This script automatically cleans up and standardizes game names, removing unnecessary characters. For example, "M.i.n_.e.c.raft" becomes "Minecraft (2011)," and is stored in a .7z file.

## Qbittorrent Integration
To configure Qbittorrent, go to "Run external command on torrent finished" and set the command to:
```
/usr/bin/python3 main.py -c %L '"%R"'
```
Note the use of both single (' ') and double (" ") quotes to handle files with spaces. It is recommended to enable the "create subfolders" option, as the script cannot directly process .rar/.zip files without it.

# Basic usage
- `-c` or `--category`: Specify the torrent's category.
```
python3 main.py -c [CATEGORY] [INPUT]
```
## Optional parameters
- `-n` or `--name`: Specify a name manually, in case our script is not able to pick up the game's name correctly. By default, the game's "release date" will be `(2000)` if this parameter is used.
- `--debug`: Enable debugging mode when executing the script. It outputs more (debugging) text to the log file, use only if necessary.

# Examples
```bash
python3 main.py -c Games /mnt/gaming/ilikethisgame/
python3 main.py -c Games /mnt/gaming/WarNe2/ -n "Warmachine 99k Sea Marine 2"
python3 main.py -c Games "/SquareRoot\ Collection\ \[Testing\ Repack\]/"
```

## Example Qbittorrent "Run on Completion" Command
```bash
/usr/bin/ssh -i /home/qbittorrent-nox/.ssh/id_rsa root@192.168.0.11 python3 /root/GameZip/main.py -c %L '"%R"'
```
This example command executes the script on a more powerful server via SSH, rather than on your NAS :)

