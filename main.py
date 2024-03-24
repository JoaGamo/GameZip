import os
import argparse
import requests
import re
import subprocess
import logging
import json
import datetime

from shutil import which
from dotenv import load_dotenv
from igdb.wrapper import IGDBWrapper
from igdb.igdbapi_pb2 import GameResult
# env
load_dotenv()
rawg_API = os.getenv("API")
categoryName = os.getenv("categoryName")
logFileLocation = os.getenv("logFileLocation")
multithread = os.getenv("multithread")

storeFolder = os.getenv("storeFolder")
# IGDB Stuff
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
# Media stuff
media1_name = os.getenv("media1_name")
media2_name = os.getenv("media2_name")
media3_name = os.getenv("media3_name")
media1_location = os.getenv("media1_location")
media2_location = os.getenv("media2_location")
media3_location = os.getenv("media3_location")

if which("7z") == None:
    compressionCMD = "7zz"
else:
    compressionCMD = "7z"


logging.basicConfig(filename=f"{logFileLocation}", format='%(asctime)s %(message)s', filemode='a')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def hardlink_files(folder_path, final_path):
    # By limitations of "ln" for folders, I decided to use 'cp -l' parameter to create hard links
    subprocess.run(f"cp -lr \'{folder_path}\' {final_path}", shell=True)


def scrub_filename(name):
    # Remove special characters and stuff between [brackets] from the name, so we can search our game's API easily.
    return re.sub(r'\[.*?\]|\W(?<!\s)|\d', '', name)


def fix_filename(file):
    if file.endswith(os.path.sep):
        file = file.rstrip(os.path.sep)
    return file



def fetch_game_name(folder_path):
    # Do note that there's no error handling or status_code checking
    # We don't want the script to continue if anything fails from this point, as it's wasted computing power
    folder_name = fix_filename(folder_path)
    folder_name = os.path.basename(folder_name)
    folder_name = scrub_filename(folder_name)
    global releaseDate
    if rawg_API == None:
        #IGDB Stuff
        r = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
        access_token = json.loads(r._content)['access_token']
        #
        result_message = IGDBWrapper(client_id, access_token).api_request('games.pb',f'search "{folder_name}"; fields name, first_release_date; limit 1;')
        result = GameResult()
        result.ParseFromString(result_message)
        for game in result.games:
            if hasattr(game, "name") and hasattr(game, "first_release_date"):
                juego = game.name
                releaseDate = game.first_release_date.seconds
                break
        
        releaseDate = datetime.datetime.fromtimestamp(releaseDate)
        releaseDate = releaseDate.year
    else:
        # RAWG Stuff
        rawg_url = "https://api.rawg.io/api/games"
        params = {"key": rawg_API, "search": folder_name}
        response = requests.get(rawg_url, params=params)
        data = response.json()
        game_info = data['results'][0]
        juego = game_info["name"]
        releaseDate = game_info.get("released", "")[:4]

    logger.debug(f"game detected was {juego}")
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
    parser.add_argument("input", help="Input file")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    args = parser.parse_args()
    folderPath = args.input
    if args.category == categoryName:
        game_name = fetch_game_name(folderPath)
        logger.info(f"Starting to compress {folderPath}")
        compression(folderPath, game_name)
        logger.info(f"Compressed {game_name} into {folderPath}")

    # This is why the script asks for a category.
    # You may want to use this script alongside your other contents to hardlink them.
    elif args.category == media1_name:
        logger.info(f"Hardlinking media1 {folderPath} to {media1_location}")
        hardlink_files(folderPath, media1_location)
    elif args.category == media2_name:
        logger.info(f"Hardlinking media2 {folderPath} to {media2_location}")
        hardlink_files(folderPath, media2_location)
    elif args.category == media3_name:
        logger.info(f"Hardlinking media3 {folderPath} to {media3_location}")
        hardlink_files(folderPath, media3_location)


if __name__ == "__main__":
    main()
