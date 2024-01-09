import os
import argparse
import requests
import logging
import re
import subprocess

#########################################
############VARIABLES####################
#########################################
API = "asw"  # RAWG API Key
storeFolder = "/wd/awd/qwe/"  # Where your files will be stored after compression,
categoryName = "Juegos"
logFileLocation = "gameZip.log"
multithread = 8  # Number of threads to use with 7z/7zz
# NOTE: IF YOU ARE USING 7zz (newer p7zip package from apt), change THIS
compressionCMD = '7zz'
# Else use 7z if using the arch AUR p7zip or something else.
#########################################
#########################################
#########################################
# Note: Debugging is VERY basic, you may want to add more ways to debug if you found a problem
logging.basicConfig(filename=f"{logFileLocation}", format='%(asctime)s %(message)s', filemode='a')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

releaseDate = None


def scrub_filename(name):
    # Remove special characters and spaces from the name
    return re.sub(r'[^\w\s]', ' ', name)


def fix_filename(file):
    if file.endswith(os.path.sep):
        file = file.rstrip(os.path.sep)
    return file


def fetch_game_name(folder_path):
    rawg_url = "https://api.rawg.io/api/games"
    folder_name = fix_filename(folder_path)
    folder_name = os.path.basename(folder_name)
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

            global releaseDate
            releaseDate = game_info.get("released", "")[:4]
    else:
        juego = None
    return juego


def compression(folder_path, game_name):
    if not os.path.exists(f"{storeFolder}{game_name} ({releaseDate}).7z"):
        compression_cmd = [f'{compressionCMD}']
        compression_cmd.extend(['a', f'{storeFolder}{game_name} ({releaseDate})', folder_path])
        compression_cmd.append(f'-mmt={multithread}')
        compression_cmd.append('-o ' + storeFolder)
        print(compression_cmd)
        subprocess.run(compression_cmd)
        logger.info(f"Successfully compressed {game_name} to {storeFolder}{game_name} {releaseDate}")
    else:
        logger.warning(f"File {storeFolder}{game_name} already exists! NOT COMPRESSING {folder_path}!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Archivo input")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    args = parser.parse_args()
    if args.category == categoryName:
        folderPath = args.input
        gameName = fetch_game_name(folderPath)
        logger.info(f"Starting to compress {folderPath}")
        compression(folderPath, gameName)
if __name__ == "__main__":
    main()
