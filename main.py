import os
import time
import requests
import logging
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from zipfile import ZipFile
from zipfile import ZIP_DEFLATED
from zipfile import ZIP_STORED
# Requires
# watchdog
# requests
#########################################
############VARIABLES####################
#########################################
API = "AAAA"  # RAWG API Key
watchFolder = "/root/test/watch/" # Folder to be observed by the script, example "/this/observe/folder/"
storeFolder = "/root/test/store/" # Where your files will be stored after compression,
                                                # example # "/thisis/compress/folder/"
logFileLocation = "gameZip.log"
doCompression = True #Set to True if you want compression, else set to False. Default = True
if doCompression:
    compressionMethod = ZIP_DEFLATED
else:
    compressionMethod = ZIP_STORED
  
# Valid Options:
# ZIP_STORED (0% compression), ZIP_DEFLATED
#########################################
#########################################
#########################################
Logging = False  # Set to True if you want Logging, debugging purposes
# Note: Debugging is VERY basic, you may want to add more ways to debug if you found a problem
# Note2: using logging.info() in code isn't a good practice
if Logging:
    logging.basicConfig(filename=f"{logFileLocation}", format='%(asctime)s %(message)s', filemode='w')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

releaseDate = None


class MyHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()

    def on_created(self, event):
        if event.is_directory:
            folder_path = event.src_path
            while not self.is_file_fully_copied(folder_path):  # This waits until the file is done copying
                time.sleep(2)
            game_name = fetch_game_name(folder_path)
            print(f"Empezando a comprimieeeeeeer {game_name} {releaseDate}")  # Debug
            compress_folder(folder_path, game_name)

    def is_file_fully_copied(self, file_path):
        # Check if the file is fully copied by waiting for it to remain unchanged for a period of time
        initial_size = os.path.getsize(file_path)
        time.sleep(5)
        return os.path.getsize(file_path) == initial_size


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
    path_to_watch = watchFolder
    event_handler = MyHandler()
    observer = Observer()
    print(f"GameZIP: Watching directory: {path_to_watch}")
    observer.schedule(event_handler, path=path_to_watch, recursive=False)
    observer.start()
    observer.join()


if __name__ == "__main__":
    main()
