#!/usr/bin/env python3
"""
Game Processor - Refactored Version
Processes game folders: fixes names via IGDB API, handles RAR extraction, and compresses for storage.
"""

import os
import re
import json
import time
import uuid
import shutil
import logging
import argparse
import datetime
import subprocess
from typing import Optional, Tuple, Dict, List, Any
from dataclasses import dataclass
from pathlib import Path

import rarfile
import requests
from dotenv import load_dotenv


# ========================= Data Classes =========================

@dataclass
class Config:
    """Configuration data class"""
    category_name: str
    log_file_location: str
    release_date: int
    multithread: str
    store_folder: str
    igdb_client_id: str
    igdb_client_secret: str
    compression_cmd: str
    password_list: List[str]
    skip_unknown_games: bool
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        load_dotenv()
        
        # Determine compression command
        from shutil import which
        compression_cmd = "7zz" if which("7z") is None else "7z"
        
        return cls(
            category_name=os.getenv("categoryName", ""),
            log_file_location=os.getenv("logFileLocation", "game_processor.log"),
            release_date=2020,
            multithread=os.getenv("multithread", "on"),
            store_folder=os.getenv("storeFolder", "./compressed/"),
            igdb_client_id=os.getenv("client_id", ""),
            igdb_client_secret=os.getenv("client_secret", ""),
            compression_cmd=compression_cmd,
            password_list=os.getenv("password_list", "").split(",") if os.getenv("password_list") else [],
            skip_unknown_games=os.getenv("SKIP_UNKNOWN_GAMES", "false").lower() == "true"
        )


@dataclass
class GameInfo:
    """Game information from IGDB"""
    name: str
    release_year: Optional[int] = None
    rating_count: int = 0
    igdb_id: Optional[int] = None


# ========================= Utilities =========================

class GameNameCleaner:
    """Handles game name cleaning and normalization"""
    
    @staticmethod
    def clean_for_search(name: str) -> str:
        """
        Clean filename for API search
        Removes special characters and content in brackets
        """
        # Remove content in brackets [like this]
        cleaned = re.sub(r'\[.*?\]', '', name)
        # Remove special characters except spaces and basic punctuation
        cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
        # Remove multiple spaces and trim
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    @staticmethod
    def clean_for_filesystem(name: str) -> str:
        """
        Clean name for filesystem compatibility
        Removes characters that might cause issues on Windows/Linux
        """
        # Remove/replace problematic characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            name = name.replace(char, '')
        # Remove trailing dots and spaces (Windows compatibility)
        name = name.rstrip('. ')
        return name[:255]  # Max filename length


class NameMatcher:
    """Handles fuzzy name matching between search terms and game titles"""
    
    @staticmethod
    def calculate_similarity_score(game_name: str, search_term: str) -> int:
        """
        Calculate similarity score between game name and search term
        Higher score = better match
        """
        game_lower = game_name.lower()
        search_lower = search_term.lower()
        
        # Exact match
        if game_lower == search_lower:
            return 1000
        
        # Remove common words for better matching
        common_words = {'the', 'of', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for'}
        game_words = set(game_lower.split()) - common_words
        search_words = set(search_lower.split()) - common_words
        
        # All search words found in game name
        if search_words and search_words.issubset(game_words):
            return 900
        
        # Game name starts with search term
        if game_lower.startswith(search_lower):
            return 800 + int(100 * len(search_lower) / len(game_lower))
        
        # Search term starts with game name
        if search_lower.startswith(game_lower):
            return 700 + int(100 * len(game_lower) / len(search_lower))
        
        # Calculate word overlap
        if game_words and search_words:
            overlap = len(game_words & search_words)
            total = len(game_words | search_words)
            if total > 0:
                return int(600 * overlap / total)
        
        # Substring matching
        if search_lower in game_lower:
            return 400 + int(100 * len(search_lower) / len(game_lower))
        
        if game_lower in search_lower:
            return 300 + int(100 * len(game_lower) / len(search_lower))
        
        return 0


# ========================= IGDB API Client =========================

class IGDBClient:
    """IGDB API client for game information retrieval"""
    
    BASE_URL = "https://api.igdb.com/v4"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.logger = logging.getLogger(__name__)
    
    def _get_access_token(self) -> str:
        """Get or refresh access token"""
        if self.access_token:
            return self.access_token
        
        response = requests.post(
            self.TOKEN_URL,
            params={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
        )
        response.raise_for_status()
        
        self.access_token = response.json()['access_token']
        return self.access_token
    
    def search_game(self, search_name: str) -> List[Dict[str, Any]]:
        """
        Search for games by name
        Returns list of matching games with their information
        """
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self._get_access_token()}',
            'Accept': 'application/json'
        }
        
        # IGDB query
        query = f'''
            search "{search_name}";
            fields name, first_release_date, total_rating_count, id;
            where game_modes != null & version_parent = null;
            limit 20;
        '''
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/games",
                headers=headers,
                data=query,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"IGDB API error: {e}")
            return []
    
    def find_best_match(self, search_name: str) -> Optional[GameInfo]:
        """
        Find the best matching game for the given search term
        """
        games = self.search_game(search_name)
        
        if not games:
            self.logger.warning(f"No games found for: {search_name}")
            return None
        
        # Score and rank games
        matcher = NameMatcher()
        scored_games = []
        
        for game in games:
            if 'name' not in game:
                continue
            
            score = matcher.calculate_similarity_score(game['name'], search_name)
            
            # Add small bonus for popularity
            rating_count = game.get('total_rating_count', 0)
            score += min(rating_count / 100, 50)  # Max 50 point bonus
            
            scored_games.append((score, game))
        
        # Sort by score and get the best match
        scored_games.sort(key=lambda x: x[0], reverse=True)
        
        if scored_games and scored_games[0][0] > 0:
            best_game = scored_games[0][1]
            
            # Parse release date
            release_year = None
            if 'first_release_date' in best_game:
                release_year = datetime.datetime.fromtimestamp(
                    best_game['first_release_date']
                ).year
            
            return GameInfo(
                name=best_game['name'],
                release_year=release_year,
                rating_count=best_game.get('total_rating_count', 0),
                igdb_id=best_game.get('id')
            )
        
        return None


# ========================= RAR Handler =========================

class RARHandler:
    """Handles RAR file detection, extraction, and cleanup"""
    
    def __init__(self, password_list: List[str]):
        self.password_list = password_list
        self.logger = logging.getLogger(__name__)
    
    def find_rar_files(self, folder_path: Path) -> Tuple[Optional[Path], List[Path]]:
        """
        Find main RAR file and all related volumes
        Returns (main_rar_path, list_of_all_parts)
        """
        folder_path = Path(folder_path)
        all_files = list(folder_path.iterdir())
        
        # Find all RAR-related files
        rar_files = []
        main_rar = None
        
        for file_path in all_files:
            filename = file_path.name.lower()
            
            # Check for main RAR file
            if filename.endswith('.rar'):
                # Check if it's a numbered part
                if not re.search(r'\.part\d+\.rar$', filename):
                    main_rar = file_path
                    
            # Collect all RAR-related files
            if (filename.endswith('.rar') or 
                re.match(r'.*\.[r-z]\d{2}$', filename)):
                rar_files.append(file_path)
        
        # If no main RAR found, look for part1
        if not main_rar and rar_files:
            part1_files = [f for f in rar_files 
                          if re.search(r'\.part0*1\.rar$', f.name.lower())]
            if part1_files:
                main_rar = part1_files[0]
        
        return main_rar, rar_files
    
    def try_passwords(self, rar_path: Path) -> Optional[str]:
        """
        Try to unlock RAR with password list
        Returns successful password or None
        """
        for password in self.password_list:
            try:
                with rarfile.RarFile(str(rar_path), 'r') as rf:
                    rf.setpassword(password)
                    # Try to read namelist to verify password
                    if rf.namelist():
                        return password
            except (rarfile.PasswordRequired, rarfile.RarWrongPassword):
                continue
            except rarfile.BadRarFile:
                self.logger.error(f"Corrupted RAR file: {rar_path}")
                raise
        
        return None
    
    def extract(self, rar_path: Path, extract_to: Path, password: Optional[str] = None) -> bool:
        """
        Extract RAR file using unrar command
        """
        cmd = ['unrar', 'x', '-y', '-o+']  # Extract with overwrite
        
        if password:
            cmd.append(f'-p{password}')
        else:
            cmd.append('-p-')  # No password
        
        cmd.extend([str(rar_path), str(extract_to) + os.sep])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            # Check if extraction created files
            if extract_to.exists() and any(extract_to.iterdir()):
                return True
            
            return False
            
        except subprocess.SubprocessError as e:
            self.logger.error(f"Extraction failed: {e}")
            return False
    
    def process_rar_archive(self, folder_path: Path) -> Tuple[bool, Optional[Path]]:
        """
        Process RAR files in folder: extract and cleanup
        Returns (success, extracted_content_path)
        """
        main_rar, all_rars = self.find_rar_files(folder_path)
        
        if not main_rar:
            return False, None
        
        self.logger.info(f"Found RAR archive: {main_rar.name}")
        
        # Create temporary extraction directory
        temp_dir = folder_path / f"temp_extract_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Check if password is needed
            password = None
            try:
                with rarfile.RarFile(str(main_rar), 'r') as rf:
                    if rf.needs_password():
                        password = self.try_passwords(main_rar)
                        if not password:
                            raise ValueError(f"Cannot unlock RAR: {main_rar.name}")
            except rarfile.NeedFirstVolume:
                # Multi-volume archive, will handle with unrar
                pass
            
            # Extract
            if not self.extract(main_rar, temp_dir, password):
                raise ValueError(f"Extraction failed: {main_rar.name}")
            
            # Move extracted contents to main folder
            for item in temp_dir.iterdir():
                dest = folder_path / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
            
            # Clean up RAR files
            for rar_file in all_rars:
                try:
                    rar_file.unlink()
                    self.logger.debug(f"Removed: {rar_file.name}")
                except OSError as e:
                    self.logger.warning(f"Cannot remove {rar_file.name}: {e}")
            
            # Find the main game folder
            dirs = [d for d in folder_path.iterdir() 
                   if d.is_dir() and not d.name.startswith('temp_')]
            
            if len(dirs) == 1:
                return True, dirs[0]
            else:
                return True, folder_path
                
        finally:
            # Cleanup temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


# ========================= Compressor =========================

class GameCompressor:
    """Handles game compression to 7z format"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def compress(self, source_path: Path, game_info: GameInfo) -> bool:
        """
        Compress game folder to 7z archive
        """
        # Prepare output filename
        game_name_clean = GameNameCleaner.clean_for_filesystem(game_info.name)
        year = game_info.release_year or self.config.release_date
        
        output_file = Path(self.config.store_folder) / f"{game_name_clean} ({year}).7z"
        
        # Check if already exists
        if output_file.exists():
            self.logger.warning(f"Archive already exists: {output_file}")
            return False
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Build compression command
        cmd = [
            self.config.compression_cmd,
            'a',  # Add to archive
            '-t7z',  # 7z format
            '-mx=5',  # Compression level (5 = normal)
            f'-mmt={self.config.multithread}',  # Multi-threading
            str(output_file),
            str(source_path) + '/*'
        ]
        
        self.logger.info(f"Compressing: {source_path.name} -> {output_file.name}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"Successfully compressed: {output_file.name}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Compression failed: {e}")
            self.logger.error(f"Output: {e.stderr}")
            
            # Clean up partial file
            if output_file.exists():
                output_file.unlink()
            
            return False


# ========================= Main Processor =========================

class GameProcessor:
    """Main game processing orchestrator"""
    
    def __init__(self, config: Config):
        self.config = config
        self.igdb_client = IGDBClient(config.igdb_client_id, config.igdb_client_secret)
        self.rar_handler = RARHandler(config.password_list)
        self.compressor = GameCompressor(config)
        self.logger = logging.getLogger(__name__)
    
    def identify_game(self, folder_path: Path, override_name: Optional[str] = None) -> Optional[GameInfo]:
        """
        Identify game from folder name using IGDB
        """
        if override_name:
            search_name = override_name
        else:
            search_name = folder_path.name
        
        # Clean name for search
        search_name_clean = GameNameCleaner.clean_for_search(search_name)
        self.logger.info(f"Searching for: '{search_name}' -> '{search_name_clean}'")
        
        # Search IGDB
        game_info = self.igdb_client.find_best_match(search_name_clean)
        
        if game_info:
            self.logger.info(
                f"Found match: {game_info.name} "
                f"({game_info.release_year or 'Unknown year'}) "
                f"[{game_info.rating_count} ratings]"
            )
            return game_info
        
        # Fallback if not found
        if self.config.skip_unknown_games:
            self.logger.warning(f"Game not found and skip_unknown_games=True")
            return None
        
        # Use folder name as fallback
        self.logger.warning(f"No IGDB match found. Using folder name: {search_name}")
        return GameInfo(
            name=search_name,
            release_year=None,
            rating_count=0
        )
    
    def process(self, folder_path: str, override_name: Optional[str] = None) -> bool:
        """
        Main processing pipeline
        """
        folder_path = Path(folder_path).resolve()
        
        if not folder_path.exists():
            self.logger.error(f"Path does not exist: {folder_path}")
            return False
        
        # Step 1: Identify game
        game_info = self.identify_game(folder_path, override_name)
        if not game_info:
            return False
        
        # Step 2: Handle RAR extraction if needed
        extraction_success, content_path = self.rar_handler.process_rar_archive(folder_path)
        
        if extraction_success:
            self.logger.info(f"Extracted RAR archive. Content path: {content_path}")
            compress_path = content_path
        else:
            self.logger.info("No RAR archive found or extraction not needed")
            compress_path = folder_path
        
        # Step 3: Compress
        return self.compressor.compress(compress_path, game_info)


# ========================= Main Entry Point =========================

def setup_logging(log_file: str, debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also output to console
        ]
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Process game folders: fix names, extract RARs, and compress"
    )
    parser.add_argument("input", help="Path to game folder")
    parser.add_argument("-c", "--category", help="Torrent category filter")
    parser.add_argument("-n", "--name", help="Override game name for search")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--force", action="store_true", help="Process even if category doesn't match")
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_env()
    
    # Setup logging
    setup_logging(config.log_file_location, args.debug)
    logger = logging.getLogger(__name__)
    
    # Check category if specified
    if args.category and not args.force:
        if args.category != config.category_name:
            logger.error(f"Category mismatch: {args.category} != {config.category_name}")
            return 1
    
    # Process the game
    try:
        processor = GameProcessor(config)
        success = processor.process(args.input, args.name)
        
        if success:
            logger.info("✓ Processing completed successfully")
            return 0
        else:
            logger.error("✗ Processing failed")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())