# GameZip

GameZip is a Python script that processes a target directory based on the specified category.
The script will use the IGDB API to correct the file name, compress the game, and store it in the directory specified in the `.env` configuration file.
GameZip is designed to be triggered by a torrent client upon torrent completion in a Linux environment but can also be executed as a standalone script.

## Configuration

> [!NOTE]
> Install the required packages using `pip install -r requirements.txt`. 
> Additionally, 7z (for handling file compression) is required on your system. For Debian systems, use `apt install p7zip`. If you are dealing with RAR files, install unrar (non-free package). Edit apt-sources to include non-free repositories, then `apt install unrar`. Note: Unlocking encrypted RAR files is not supported in unrar-free, in case you install it.

> [!WARNING]
> By design, when handling RAR files, this script will DELETE all RAR files inside the directory to be compressed.

1. **Rename** `.env.example` to `.env` and configure the following fields:

    - `multithread`: Set the number of CPU threads for 7z to use during compression.
    - `IGDB fields`: [read here how to get them](https://api-docs.igdb.com/#account-creation)
    - `categoryName`: The category name for your torrent's games. This ensures the script only compresses game files and not other types of files.
    - `storeFolder`: The directory where the script will store the compressed and renamed versions of the games.

This script automatically cleans up and standardizes game names, removing unnecessary characters. For example, "M.i.n_.e.c.raft" becomes "Minecraft (2011)," and is stored in a .7z file.

## Qbittorrent Integration

To configure Qbittorrent, go to "Run external command on torrent finished" and set the command to:

```bash
/usr/bin/python3 main.py -c %L '"%R"'
```

Note the use of both single (' ') and double (" ") quotes to handle files with spaces. It is recommended to enable the "create subfolders" option, as the script can not directly process .rar/.zip files without it.

## Basic usage

- `-c` or `--category`: Specify the torrent's category.

```bash
python3 main.py -c [CATEGORY] [INPUT]
```

## Optional parameters

- `-n` or `--name`: Specify a name manually, in case our script is not able to pick up the game's name correctly. By default, the game's "release date" will be `(2020)` if this parameter is used.
- `--debug`: Enable debugging mode when executing the script. It outputs more (debugging) text to the log file, use only if necessary.

## Examples

```bash
python3 main.py -c Games /mnt/gaming/ilikethisgame/
python3 main.py -c Games /mnt/gaming/WarNe2/ -n "Warmachine 99k Negotiation Marine 2"
python3 main.py -c Games "/SquareRoot\ Collection\ \[Testing\ Repack\]/"
```

## Example Qbittorrent "Run on Completion" Command

This example executes the script on a more powerful server via SSH, instead of using a low-powered NAS :)

```bash
/usr/bin/ssh -i /home/qbittorrent-nox/.ssh/id_rsa gamezip@192.168.0.11 python3 /gamezip/main.py -c %L '"%R"'
```
