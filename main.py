import os
import argparse
import requests
import logging
import re
from zipfile import ZipFile
from zipfile import ZIP_DEFLATED
from zipfile import ZIP_STORED

#########################################
############VARIABLES####################
#########################################
API = "huh"  # RAWG API Key
storeFolder = "huh"  # Where your files will be stored after compression, example /mnt/folder/location/
categoryName = "Juegos"
logFileLocation = "gameZip.log"
doCompression = True
if doCompression:
    compressionMethod = ZIP_DEFLATED
else:
    compressionMethod = ZIP_STORED
# Valid Options:
# ZIP_STORED (0% compression), ZIP_DEFLATE, ZIP_LZMA
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
    api_key = API
    rawg_url = "https://api.rawg.io/api/games"
    folder_name = os.path.basename(folder_path)
    folder_name = scrub_filename(folder_name)
    # API request
    params = {"key": api_key, "search": folder_name}
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


def compress_folder(folder_path, game_name):
    zip_filename = f"{storeFolder}{game_name} ({releaseDate}).zip"
    print(f"Starting to compress {game_name} ({releaseDate}) to {storeFolder}")
    if Logging:
        logging.info(f"Starting to compress {game_name} to {storeFolder}")
    try:
        with ZipFile(zip_filename, 'x', compressionMethod) as zip_file:
            for folder_root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(folder_root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zip_file.write(file_path, arcname=arcname)
    except FileExistsError:
        print(f"The file already exists!, NOT compressing {game_name}")

    print(f"{game_name} compressed successfully")
    if Logging:
        logging.info(f"Game '{game_name}'' has been compressed successfully!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file location")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    parser.add_argument("-o", "--output", action="store", help="Where to output")
    args = parser.parse_args()
    if args.category == {categoryName}:
        folderPath = args.input
        gameName = fetch_game_name(folderPath)
        global storeFolder
        if args.output:
            storeFolder = args.output
        compress_folder(folderPath, gameName)


if __name__ == "__main__":
    main()
