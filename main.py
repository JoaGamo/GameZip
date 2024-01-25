import os
import argparse
import requests
import re
import subprocess
import logging
from dotenv import load_dotenv

# env
load_dotenv()
API = os.getenv("API")
categoryName = os.getenv("categoryName")
logFileLocation = os.getenv("logFileLocation")
multithread = os.getenv("multithread")
compressionCMD = os.getenv("compressionCMD")
storeFolder = os.getenv("storeFolder")
#
# Note: Debugging is VERY basic, you may want to add more ways to debug if you found a problem
logging.basicConfig(filename=f"{logFileLocation}", format='%(asctime)s %(message)s', filemode='a')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def scrub_filename(name):
    # Remove special characters and spaces from the name
    return re.sub(r'[^\w\s]', '', name)


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

            global releaseDate  # Game's release date
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
        subprocess.run(compression_cmd)
        logger.info(f"Successfully compressed {game_name} to {storeFolder}{game_name} {releaseDate}")
    else:
        logger.warning(f"File {storeFolder}{game_name} already exists! NOT COMPRESSING {folder_path}!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Archivo input")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    args = parser.parse_args()
    folderPath = args.input
    if args.category == categoryName:
        gameName = fetch_game_name(folderPath)
        logger.info(f"Starting to compress {folderPath}")
        compression(folderPath, gameName)


if __name__ == "__main__":
    main()
