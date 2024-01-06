import os
import argparse
import requests
import logging
import re
import subprocess
#########################################
############VARIABLES####################
#########################################
API = "asd"  # RAWG API Key
storeFolder = "/asd/dfw/hfh/"  # Where your files will be stored after compression,
categoryName = "Juegos"
logFileLocation = "gameZip.log"
multithread = 8 #Number of threads to use with 7z/7zz
# NOTE: IF YOU ARE USING 7zz (newer p7zip package from apt), change THIS
compressionCMD = '7z'
# Else use 7z if using the arch AUR p7zip or something else.
#########################################
#########################################
#########################################
Logging = False  # Set to True if you want Logging, debugging purposes
# Note: Debugging is VERY basic, you may want to add more ways to debug if you found a problem
# Note2: using logging.info() in code isn't a good practice according to what i've read, I have no need to change it so.
if Logging:
    logging.basicConfig(filename=f"{logFileLocation}", format='%(asctime)s %(message)s', filemode='w')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
releaseDate = None


def scrub_filename(name):
    # Remove special characters and spaces from the name
    return re.sub(r'[^\w\s]', '', name)


def fetch_game_name(folder_path):
    rawg_url = "https://api.rawg.io/api/games"
    folder_name = os.path.basename(folder_path)
    folder_name = scrub_filename(folder_name)
    # API request
    params = {"key": API, "search": folder_name}
    response = requests.get(rawg_url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data['results']:
            game_info = data['results'][0]
            juego = game_info["name"]
            juego = scrub_filename(juego)

            global releaseDate  # Game's release date
            releaseDate = game_info.get("released", "")[:4]
    else:
        juego = None
    return juego


def compression(folder_path, game_name):
    compression_cmd = [f'{compressionCMD}']
    compression_cmd.extend(['a', f'{storeFolder}{game_name} ({releaseDate})', folder_path])
    compression_cmd.append(f'-mmt={multithread}')
    compression_cmd.append('-o ' + storeFolder)
    print(compression_cmd)
    subprocess.run(compression_cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Archivo input")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    args = parser.parse_args()
    if args.category == categoryName:
        folderPath = args.input
        gameName = fetch_game_name(folderPath)
        compression(folderPath, gameName)


if __name__ == "__main__":
    main()
