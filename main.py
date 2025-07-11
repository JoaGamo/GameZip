import os
import argparse
import requests
import re
import subprocess
import logging
import json
import datetime
import rarfile
import uuid 
import shutil
import time

from shutil import which
from dotenv import load_dotenv
from igdb.wrapper import IGDBWrapper
from igdb.igdbapi_pb2 import GameResult


def load_config():
    load_dotenv()
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
        "releaseDate": 2020,
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
        "compressionCMD": "7zz" if which("7z") is None else "7z",
        "password_list": os.getenv("password_list", "").split(",")
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
    original_folder_name = folder_name
    folder_name = scrub_filename(folder_name)
    logger.debug(f"Name obtained from directory's name: {folder_name}")
    game = None
    
    if rawg_API is not None:
        # RAWG Stuff
        rawg_url = "https://api.rawg.io/api/games"
        params = {"key": rawg_API, "search": folder_name}
        try:
            response = requests.get(rawg_url, params=params)
            if response.status_code != 200:
                raise ConnectionError(f"RAWG Status code: {response.status_code}")
            data = response.json()
            
            # Check if results exist and are not empty
            if data.get('results') and len(data['results']) > 0:
                game_info = data['results'][0]
                game = game_info["name"]
                releaseDate = game_info.get("released", "")[:4] if game_info.get("released") else str(releaseDate)
                logger.debug(f"Name obtained from RAWG's API: {game} releaseDate={releaseDate}")
            else:
                logger.warning(f"No results found for game '{folder_name}' in RAWG database")
                
        except Exception as e:
            logger.error(f"Error fetching from RAWG API: {str(e)}")
            
    else:
        # IGDB Stuff
        try:
            r = requests.post(
                f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
            if r.status_code != 200:
                raise ConnectionError(f"Token request failed with status {r.status_code}")
            access_token = json.loads(r.content)['access_token']
            query =f'''
                search "{folder_name}"; 
                fields name,first_release_date,alternative_names.name,popularity; 
                where category = (0,4) & version_parent = null;
                sort popularity desc;
                limit 6;
                '''
            result_message = IGDBWrapper(client_id, access_token).api_request('games.pb', query)
            result = GameResult()
            result.ParseFromString(result_message)
            
            best_match = None
            for game_result in result.games:
                if hasattr(game_result, "name"):
                    if folder_name.lower() in game_result.name.lower() or game_result.name.lower() in folder_name.lower():
                        best_match = game_result
                        break
            
            if not best_match and result.games:
                best_match = result.games[0]
            
            if best_match:
                game = best_match.name
                releaseDate = best_match.first_release_date.seconds if hasattr(best_match, "first_release_date") else None
                if releaseDate:
                    releaseDate = datetime.datetime.fromtimestamp(releaseDate).year
                logger.debug(f"Name obtained from IGDB's API: {game} releaseDate={releaseDate}")

            if not game:
                logger.warning(f"No results found for game '{folder_name}' in IGDB database")
                
        except Exception as e:
            logger.error(f"Error fetching from IGDB API: {str(e)}")
            logger.debug(f"Query used: {query if 'query' in locals() else 'Query not defined'}")
            logger.debug(f"Folder name searched: {folder_name}")
    
    # Fallback: use original folder name if API search failed
    if not game:
        game = original_folder_name
        logger.warning(f"API search failed. Using original folder name as fallback: {game}")
        # Set a default release date if we couldn't get one from API
        releaseDate = config.get("releaseDate", 2020)
    # Some games have special characters in their names, so we need to scrub them for Windows compatibility.
    game = scrub_filename(game)
    config["releaseDate"] = releaseDate
    return game


def find_rar_files(folder_path):
    """
    Find all RAR files in the folder, including split volumes.
    Returns the main RAR file and a list of all related volumes.
    Handles extended sequences: .rar, .r00-.r99, .s00-.s99, .t00-.t99, etc.
    """
    all_files = os.listdir(folder_path)
    
    main_rar = None
    rar_files = []
    
    # Function to check if a file is a RAR part file
    def is_rar_part(filename):
        return bool(re.match(r'.*\.[r-z]\d{2}$', filename, re.IGNORECASE))
    
    # Function to check if a file is a numbered part file
    def is_part_numbered(filename):
        return bool(re.match(r'.*\.part\d+\.rar$', filename, re.IGNORECASE))
    
    # First, try to find the main RAR file
    for file in all_files:
        # Skip part files when looking for main RAR
        if is_rar_part(file) or is_part_numbered(file):
            continue
            
        if file.lower().endswith('.rar'):
            main_rar = os.path.join(folder_path, file)
            break
    
    # If no main RAR found, check if we have split files
    if not main_rar:
        # Look for any file with .r00 through .z99 extension
        r_files = [f for f in all_files if is_rar_part(f)]
        if r_files:
            # For this format, the main file should be .rar
            base_name = re.sub(r'\.[r-z]\d{2}$', '', r_files[0], flags=re.IGNORECASE)
            potential_main = f"{base_name}.rar"
            if potential_main in all_files:
                main_rar = os.path.join(folder_path, potential_main)
    
    # If still no main RAR found, check for numbered part files
    if not main_rar:
        part_files = [f for f in all_files if is_part_numbered(f)]
        if part_files:
            # Sort part files to ensure the first part is selected as main
            part_files.sort(key=lambda x: int(re.search(r'\.part(\d+)\.rar$', x).group(1)))
            main_rar = os.path.join(folder_path, part_files[0])

    if not main_rar:
        return None, []
    
    # Get the base name without extension
    main_base = re.sub(r'\.rar$', '', os.path.basename(main_rar))
    
    # Now collect all related RAR parts
    for file in all_files:
        full_path = os.path.join(folder_path, file)
        
        # Skip the main RAR file as we already have it
        if full_path == main_rar:
            continue
            
        # Check if this file belongs to the same RAR set
        if is_rar_part(file) or is_part_numbered(file) or file.lower().endswith('.rar'):
            # Get the base name of this file
            if is_rar_part(file):
                file_base = re.sub(r'\.[r-z]\d{2}$', '', file)
            elif is_part_numbered(file):
                file_base = re.sub(r'\.part\d+\.rar$', '', file)
            else:
                file_base = re.sub(r'\.rar$', '', file)
                
            # If the base names match, this is part of our RAR set
            if file_base.lower() == main_base.lower():
                rar_files.append(full_path)
    
    logger.debug(f"Found main RAR: {main_rar}")
    logger.debug(f"Found RAR parts: {rar_files}")
    
    # Sort the RAR files to ensure proper order
    def rar_sort_key(path):
        filename = os.path.basename(path).lower()
        if '.part' in filename:
            match = re.search(r'\.part(\d+)\.rar$', filename)
            return (1, int(match.group(1)) if match else 0)
        elif re.match(r'.*\.[r-z]\d{2}$', filename):
            match = re.search(r'\.([r-z])(\d{2})$', filename)
            if match:
                letter, number = match.groups()
                letter_value = (ord(letter.lower()) - ord('r')) * 100
                return (2, letter_value + int(number))
        return (0, 0)  # Main .rar file comes first
    
    rar_files = sorted(rar_files, key=rar_sort_key)
    
    # Add main RAR to the beginning of the list
    all_rar_files = [main_rar] + rar_files
    
    return main_rar, all_rar_files


def try_unlock_rar(rar_file, password_list):
    for password in password_list:
        logger.debug(f"Trying password: {password}")
        try:
            with rarfile.RarFile(rar_file, 'r') as rf:
                logger.debug(f"Attempting to list contents with password: {password}")
                rf.setpassword(password)

                if len(rf.namelist()) == 0:
                    raise rarfile.RarWrongPassword("Wrong password")
                logger.debug(f"Successfully unlocked RAR with password: {password}")
                return password
        except rarfile.BadRarFile:
            logger.error(f"File {rar_file} is corrupted")  
            raise
        except (rarfile.PasswordRequired, rarfile.RarWrongPassword):
            logger.debug(f"Password {password} is incorrect")
            continue
            
    logger.warning("Failed to unlock RAR with any provided password")
    return None 


def extract_rar(rar_path, extract_path, config):
    """
    Extract RAR file to the specified path.
    Returns True if extraction was successful, False otherwise.
    """
    command = ['unrar', 'x', '-y']
    password = None
    
    try:
        with rarfile.RarFile(rar_path, 'r') as rf:
            if rf.needs_password():
                password = try_unlock_rar(rar_path, config["password_list"])
                if not password:
                    raise ValueError(f"Failed to unlock RAR file: {rar_path}")
                command.extend([f'-p{password}'])
        
        command.extend([rar_path, extract_path])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if "is not RAR archive" not in error_msg:  # Ignore expected errors for split archives
                logger.warning(f"Extraction warning: {error_msg}")
        
        # Verify extraction success by checking if files were created
        if not os.listdir(extract_path):
            raise subprocess.CalledProcessError(1, command, "Extraction failed - no files extracted")
        
        logger.info(f"Successfully extracted RAR file: {rar_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        print("Failed to extract RAR file, check your logs for more info")
        logger.error(f"Failed to extract RAR file: {rar_path}. Error: {e}")
        logger.error(f"Extraction of {rar_path} may have had issues. Output: {e.output}")
        raise


def handle_rar_file(folder_path, game_name, config):
    """
    Handle RAR file extraction and cleanup.
    Returns (success, root_folder) tuple.
    """
    main_rar, rar_files = find_rar_files(folder_path)
    if not main_rar:
        logger.info(f"No RAR files found in {folder_path}. Proceeding with normal compression.")
        return False, None

    # Create a unique subdirectory for extraction
    temp_dir_name = f"temp_extract_{uuid.uuid4().hex}"
    extract_dir = os.path.join(folder_path, temp_dir_name)
    os.makedirs(extract_dir, exist_ok=True)
    
    extraction_successful = False
    root_folder = None

    try:
        if extract_rar(main_rar, extract_dir, config):
            logger.info(f"Successfully extracted RAR file: {main_rar}")
            
            # Move extracted contents to the original folder
            for item in os.listdir(extract_dir):
                s = os.path.join(extract_dir, item)
                d = os.path.join(folder_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            logger.info(f"Moved extracted contents to {folder_path}")
            
            extraction_successful = True
            
            # Clean up RAR files only after successful extraction and copying
            for rar_file in [main_rar] + rar_files:
                try:
                    os.remove(rar_file)
                    logger.debug(f"Removed RAR file: {rar_file}")
                except OSError as e:
                    logger.warning(f"Failed to remove RAR file {rar_file}: {e}")
            
            # Determine the root folder for compression
            # Explicitly exclude the temporary directory from the search
            directories = [d for d in os.listdir(folder_path) 
                         if os.path.isdir(os.path.join(folder_path, d)) 
                         and d != temp_dir_name]
            
            if len(directories) == 1:
                root_folder = directories[0]
                logger.info(f"First directory inside {folder_path} is {root_folder}")
            elif len(directories) > 1:
                logger.warning(f"Multiple directories found inside {folder_path}. Using original folder path.")
                root_folder = os.path.basename(folder_path)
            else:
                logger.warning(f"No directories found inside {folder_path}. Using original folder path.")
                root_folder = os.path.basename(folder_path)
                
    except Exception as e:
        logger.error(f"Error during RAR handling: {str(e)}")
        raise
    finally:
        # Clean up temporary extraction directory only if it exists
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
                logger.debug("Cleaned up temporary extraction directory")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary directory {extract_dir}: {e}")
    
    return extraction_successful, root_folder



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
    logger.debug (f"Loaded passwords: {config['password_list']}")
    # Sleep 10 seconds, fixes a bug in my CephFS that provoked file corruption.
    time.sleep(10)

    if args.category == config["category_name"]:
        try:
            if args.name:
                game_name = args.name
            else:
                game_name = fetch_game_name(folder_path, config)
            
            success, root_folder = handle_rar_file(folder_path, game_name, config)
            if success:
                compression_path = os.path.join(folder_path, root_folder) if root_folder else folder_path
                logger.info(f"  Starting compression from {compression_path}")
                compression(compression_path, game_name, config)
                logger.info(f"Successfully compressed {game_name}")
            else:
                logger.info(f"No RAR handling needed. Starting direct compression from {folder_path}")
                compression(folder_path, game_name, config)
                logger.info(f"Successfully compressed {game_name}")
                
        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            logger.error(f"Failed to process {folder_path}")
            
            raise SystemExit(1)
        
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
