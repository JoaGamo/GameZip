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


def load_config():
    load_dotenv()
    # media_names = os.getenv("media_names").split(",")
    # media_locations = os.getenv("media_locations").split(",")

    media_names = os.getenv("media_names", "").split(",") if os.getenv("media_names") else []
    media_locations = os.getenv("media_locations", "").split(",") if os.getenv("media_locations") else []

    if len(media_names) != len(media_locations):
        logger.warning(
            "Mismatch between media_names and media_locations lengths. Ensure both lists are of the same length.")

    media_dict = dict(zip(media_names, media_locations))

    config = {
        "rawg_API": os.getenv("API"),
        "category_name": os.getenv("categoryName"),
        "logFileLocation": os.getenv("logFileLocation"),
        "releaseDate": 2000,
        "multithread": os.getenv("multithread"),
        "storeFolder": os.getenv("storeFolder"),
        "igdb": {
            "client_id": os.getenv("client_id"),
            "client_secret": os.getenv("client_secret")
        },
        "media": {
            "media_names": media_names,
            "media_locations": media_locations
        },
        "compressionCMD": "7zz" if which("7z") is None else "7z"
    }
    return config, media_dict


def load_logger(config, debug_mode):
    global logger
    logging.basicConfig(filename=config["logFileLocation"], format='%(asctime)s %(message)s', filemode='a')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if debug_mode:
        logger.setLevel(logging.DEBUG)


def hardlink_files(folder_path, final_path):
    # By limitations of "ln" for folders, I decided to use 'cp -l' parameter to create hard links
    subprocess.run(f"cp -lr \'{folder_path}\' {final_path}", shell=True)
    logger.debug(f"Successfully hard-linked file from source directory {folder_path} to target path {final_path}")


def scrub_filename(name):
    # Remove special characters and stuff between [brackets] from the name, so we can search our game's API easily.
    return re.sub(r'\[.*?\]|\W(?<!\s)|\d', '', name)


def fix_filename(file):
    if file.endswith(os.path.sep):
        file = file.rstrip(os.path.sep)
    return file


def fetch_game_name(folder_path, config):
    client_id = config["igdb"]['client_id']
    client_secret = config["igdb"]['client_secret']
    releaseDate = 2000
    rawg_API = config["rawg_API"]

    folder_name = fix_filename(folder_path)
    folder_name = os.path.basename(folder_name)
    folder_name = scrub_filename(folder_name)
    logger.debug(f"Name obtained from directory's name: {folder_name}")
    if rawg_API is not None:
        # RAWG Stuff
        rawg_url = "https://api.rawg.io/api/games"
        params = {"key": rawg_API, "search": folder_name}
        response = requests.get(rawg_url, params=params)
        if response.status_code != 200:
            raise ConnectionError(f"RAWG Status code: {response.status_code}")
        data = response.json()
        if data['results'] is None:
            logging.error(f"Could not find game {folder_name} in RAWG database")
            raise ValueError(f"Could not find the game {folder_name} in RAWG Database")
        game_info = data['results'][0]
        game = game_info["name"]
        releaseDate = game_info.get("released", "")[:4]
        logger.debug(f"Name obtained from RAWG's API: {game} releaseDate={releaseDate}")
    else:
        # IGDB Stuff
        r = requests.post(
            f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
        access_token = json.loads(r._content)['access_token']
        result_message = IGDBWrapper(client_id, access_token).api_request('games.pb',
                                                                          f'search "{folder_name}"; fields name, first_release_date; limit 1;')
        result = GameResult()
        result.ParseFromString(result_message)
        for game in result.games:
            if hasattr(game, "name") and hasattr(game, "first_release_date"):
                game = game.name
                releaseDate = game.first_release_date.seconds
                break
        releaseDate = datetime.datetime.fromtimestamp(releaseDate)
        releaseDate = releaseDate.year
        logger.debug(f"Name obtained from IGDB's API: {game} releaseDate={releaseDate}")

    config["releaseDate"] = releaseDate
    return game


def compression(folder_path, game_name, config):
    store_folder = config["storeFolder"]
    multithread = config["multithread"]
    release_date = config["releaseDate"]

    if not os.path.exists(f"{store_folder}{game_name} ({release_date}).7z"):
        compression_cmd = [config["compressionCMD"]]
        compression_cmd.extend(['a', f'{store_folder}{game_name} ({release_date})', folder_path])
        compression_cmd.append(f'-mmt={multithread}')
        compression_cmd.append('-o ' + store_folder)
        subprocess.run(compression_cmd)
        logger.info(f"Successfully compressed {game_name} to {store_folder}{game_name} {release_date}")
    else:
        logger.warning(f"File {store_folder}{game_name} already exists! Skipping compression of {folder_path}!")


def main():
    config, media_dict = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    parser.add_argument("-n", "--name", action="store", help="Provide the file's name in case we can't pick it up")
    parser.add_argument("--debug", action="store_true", help="Enable non-interactive debugging mode")
    args = parser.parse_args()
    load_logger(config, args.debug)
    folder_path = args.input

    if args.category == config["category_name"]:
        game_name = args.name
        if args.name is None:
            game_name = fetch_game_name(folder_path, config)
        logger.info(f"Starting to compress source directory {folder_path} into {config["storeFolder"]}")
        compression(folder_path, game_name, config)
        logger.info(f"Compressed {game_name} from source directory {folder_path} into {config["storeFolder"]}")
        exit()

    # This is why the script asks for a category.
    # You may want to use this script alongside your other contents to hardlink them.
    if args.category in config["media"]['media_names']:
        location = media_dict.get(args.category, None)
        if location:
            logger.info(f"Hardlinking {args.category} {folder_path} to {location}")
            hardlink_files(folder_path, location)
        else:
            logger.error(f"Location not found for category: {args.category}")
    else:
        logger.error(f"Unknown category: {args.category}")


if __name__ == "__main__":
    main()
