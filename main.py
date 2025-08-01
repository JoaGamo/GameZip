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


def load_config():
    load_dotenv()
    config = {
        "category_name": os.getenv("categoryName"),
        "logFileLocation": os.getenv("logFileLocation"),
        "releaseDate": 2020,
        "multithread": os.getenv("multithread"),
        "storeFolder": os.getenv("storeFolder"),
        "igdb": {
            "client_id": os.getenv("client_id"),
            "client_secret": os.getenv("client_secret")
        },
        "compressionCMD": "7zz" if which("7z") is None else "7z",
        "password_list": os.getenv("password_list", "").split(","),
        
        # Popularity filter settings - only check how many ratings/reviews a game has
        "enable_popularity_filter": os.getenv("ENABLE_POPULARITY_FILTER", "false").lower() == "true",
        "skip_unknown_games": os.getenv("SKIP_UNKNOWN_GAMES", "false").lower() == "true",
        "popularity_filters": {
            "min_igdb_rating_count": int(os.getenv("MIN_IGDB_RATING_COUNT", "100")),
        }
    }
    return config


def load_logger(config, debug_mode):
    global logger
    logging.basicConfig(filename=config["logFileLocation"], format='%(asctime)s %(message)s', filemode='a')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if debug_mode:
        logger.setLevel(logging.DEBUG)

def scrub_filename(name):
    # Remove special characters and stuff between [brackets] from the name, so we can search our game's API easily.
    cleaned = re.sub(r'\[.*?\]|\W(?<!\s)|\d', '', name)
    # Remove spaces at the end
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def fix_filename(file):
    if file.endswith(os.path.sep):
        file = file.rstrip(os.path.sep)
    return file


def find_best_match(games, search_name):
    """
    Find the best matching game from a list of games based on name similarity.
    Returns the best matching game or None if no matches found.
    """
    def calculate_match_score(game_name, search_name):
        """Calculate how well a game name matches the search term"""
        game_lower = game_name.lower()
        search_lower = search_name.lower()
        
        # Exact match gets highest score
        if game_lower == search_lower:
            return 1000
        
        # Game name starts with search term and is not much longer
        if game_lower.startswith(search_lower):
            length_ratio = len(search_lower) / len(game_lower)
            if length_ratio > 0.8:  # Game name is not much longer than search term
                return 900
            elif length_ratio > 0.6:
                return 800
            else:
                return 400  # Much longer, less relevant
        
        # Search term starts with game name - be more strict here
        if search_lower.startswith(game_lower):
            length_ratio = len(game_lower) / len(search_lower)
            # Only give high score if the game name is a significant part
            if length_ratio > 0.8:  # Game name is almost as long as search term
                return 850
            elif length_ratio > 0.6:
                return 750
            elif length_ratio > 0.4:  # Still substantial portion
                return 400
            else:
                return 150  # Game name is too short compared to search term
        
        # Game name contains search term as whole word
        if f" {search_lower} " in f" {game_lower} ":
            return 600
        
        # Search term contains game name as whole word - be very strict
        if f" {game_lower} " in f" {search_lower} ":
            length_ratio = len(game_lower) / len(search_lower)
            if length_ratio > 0.5:  # Game name is substantial part of search
                return 500
            else:
                return 200  # Game name is small part of search
        
        # Partial matches with length consideration
        if search_lower in game_lower:
            length_ratio = len(search_lower) / len(game_lower)
            if length_ratio > 0.7:  # Search term is a significant part of game name
                return 300
            else:
                return 150  # Search term is a small part of game name
        
        # Game name contained in search term - very strict penalties
        if game_lower in search_lower:
            length_ratio = len(game_lower) / len(search_lower)
            if length_ratio > 0.7:  # Game name is a significant part of search term
                return 250
            elif length_ratio > 0.4:  # Moderate portion
                return 150
            else:
                return 50  # Game name is a very small part of search term
        
        # No match
        return 0
    
    best_match = None
    best_score = -1
    
    # Find the best match based on name similarity first, then popularity
    logger.debug(f"games found from API: {games}")
    for game_result in games:
        if 'name' in game_result:
            match_score = calculate_match_score(game_result['name'], search_name)
            logger.debug(f"Match score for '{game_result['name']}' against '{search_name}': {match_score}")
            
            if match_score > 0:  # Only consider games that match
                rating_count = game_result.get('total_rating_count', 0)
                # Combine match score with popularity (match score is weighted much higher)
                total_score = match_score + (rating_count / 10)  # popularity bonus
                
                if total_score > best_score:
                    best_match = game_result
                    best_score = total_score
    
    # If no name matches found, fall back to the most popular game
    if not best_match and games:
        best_rating_count = -1
        for game_result in games:
            rating_count = game_result.get('total_rating_count', 0)
            if rating_count > best_rating_count:
                best_match = game_result
                best_rating_count = rating_count
        
        # If still no match (all have 0 ratings), take the first one
        if not best_match:
            best_match = games[0]
    
    return best_match


def fetch_game_name(folder_path, config):
    client_id = config["igdb"]['client_id']
    client_secret = config["igdb"]['client_secret']
    releaseDate = 2020
    folder_name = fix_filename(folder_path)
    folder_name = os.path.basename(folder_name)
    original_folder_name = folder_name
    folder_name = scrub_filename(folder_name)
    logger.debug(f"Name obtained from directory's name: {folder_name}")
    game = None
    
    try:
        r = requests.post(
            f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
        if r.status_code != 200:
            raise ConnectionError(f"Token request failed with status {r.status_code}")
        access_token = json.loads(r.content)['access_token']
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        query = f'''search "{folder_name}"; 
            fields name,first_release_date,alternative_names.name, total_rating_count;                 
            where game_type = (0, 4) & version_parent = null;
            limit 10;
            '''
            
        res = requests.post('https://api.igdb.com/v4/games', headers=headers, data=query)
        res.raise_for_status()
        games = res.json()
        logger.debug(games)
        
        
        best_match = find_best_match(games, folder_name)
        
        if best_match:
            game = best_match['name']
            releaseDate = best_match['first_release_date'] if 'first_release_date' in best_match else None
            if releaseDate:
                releaseDate = datetime.datetime.fromtimestamp(releaseDate).year
            logger.info(f"Name obtained from IGDB's API: {game} releaseDate={releaseDate} ratings={best_match.get('rating_count', 0)}")
            is_popular, reason = quality_check(best_match, config)
            if not is_popular:
                logger.warning(f"Game '{game}' filtered out: {reason}")
                raise ValueError(f"Game popularity filter failed: {reason}")
            logger.info(f"Game '{game}' passed popularity check: {best_match.get('total_rating_count', 0)} ratings")


        if not game:
            logger.warning(f"No results found for game '{folder_name}' in IGDB database")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error fetching from IGDB API: {str(e)}")
        logger.error(f"Folder name searched: {folder_name}")
        logger.debug(f"Query used: {query if 'query' in locals() else 'Query not defined'}")

    # Fallback: use original folder name if API search failed
    if not game:
        if config.get("skip_unknown_games", False):
            logger.warning(f"Game not found in API and skip_unknown_games is enabled")
            raise ValueError("Game not found in API and skip_unknown_games is enabled")
            
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
    
    def is_rar_part(filename):
        return bool(re.match(r'.*\.[r-z]\d{2}$', filename, re.IGNORECASE))
    
    def is_part_numbered(filename):
        return bool(re.match(r'.*\.part\d+\.rar$', filename, re.IGNORECASE))
    
    # First, try to find the main RAR file
    for file in all_files:
        if is_rar_part(file) or is_part_numbered(file):
            continue
            
        if file.lower().endswith('.rar'):
            main_rar = os.path.join(folder_path, file)
            break
    
    if not main_rar:
        # Look for any file with .r00 through .z99 extension
        r_files = [f for f in all_files if is_rar_part(f)]
        if r_files:
            # For this format, the main file should be .rar
            base_name = re.sub(r'\.[r-z]\d{2}$', '', r_files[0], flags=re.IGNORECASE)
            potential_main = f"{base_name}.rar"
            if potential_main in all_files:
                main_rar = os.path.join(folder_path, potential_main)
    
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


def quality_check(game_data, config):
    """
    Checks if this game is popular enough (has enough ratings/reviews).
    Returns (is_popular, reason) tuple.
    """
    if not config.get("enable_popularity_filter", False):
        return True, "Popularity filter disabled"

    popularity_config = config.get("popularity_filters", {})
    
    rating_count = game_data.get("total_rating_count", 0)
    min_rating_count = popularity_config.get("min_igdb_rating_count", 100)
    
    if rating_count < min_rating_count:
        return False, f"Not popular enough - only {rating_count} ratings (minimum: {min_rating_count})"

    return True, f"Game is popular enough with {rating_count} ratings"


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
    config = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file")
    parser.add_argument("-c", "--category", action="store", help="Torrent category")
    parser.add_argument("-n", "--name", action="store", help="Provide the file's name in case we can't pick it up")
    parser.add_argument("--debug", action="store_true", help="Enable non-interactive debugging mode")
    parser.add_argument("--force-compress", action="store_true", help="Bypass popularity filters")
    args = parser.parse_args()
    load_logger(config, args.debug)
    folder_path = args.input
    logger.debug(f"Loaded passwords: {config['password_list']}")
    if args.force_compress:
        config["enable_popularity_filter"] = False
        logger.info("Popularity filters bypassed due to --force-compress flag")
    
    # This simple 10s fixes an unknown bug in my setup that caused file corruption
    print("Waiting 10 seconds to ensure all files are ready...")
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
        except ValueError as e:
            if "popularity filter" in str(e).lower() or "skip_unknown_games" in str(e).lower():
                logger.info(f"Game skipped: {e}")
                return  # Exit gracefully, don't treat as error
            else:
                raise
        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            logger.error(f"Failed to process {folder_path}")
            raise SystemExit(1)
    else:
        logger.error(f"Unknown category: {args.category}")


if __name__ == "__main__":
    main()
