# Test cases for game_processor_refactored.py

import os
import shutil
import tempfile
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Import the components to test
import importlib.util, sys
spec = importlib.util.spec_from_file_location('game_processor_refactored', '/home/joaco/VisualCode/GameZip/game_processor_refactored.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GameProcessor = mod.GameProcessor
Config = mod.Config
IGDBClient = mod.IGDBClient
RARHandler = mod.RARHandler


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    dir = Path(tempfile.mkdtemp(prefix='game_processor_test_'))
    yield dir
    shutil.rmtree(dir)

def create_dummy_file(path: Path, size_mb: int = 1) -> Path:
    """Create a dummy file of specified size in MB"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x00' * (size_mb * 1024 * 1024))
    return path

@patch.object(IGDBClient, 'find_best_match')
def test_plain_file_case(mock_igdb, temp_dir):
    """Test processing a folder with SCENE naming containing a 1MB dummy file (no RAR)"""
    # Setup output directory
    output_dir = temp_dir / 'output'
    output_dir.mkdir()
    
    # Create game folder with SCENE naming and dummy file
    game_folder = temp_dir / 'Minecraft [FitGirl Repack]'
    dummy_file = create_dummy_file(game_folder / 'dummy.dat')
    
    # Mock IGDB client to return a game info
    from dataclasses import dataclass
from typing import Optional

@dataclass
class MockGameInfo:
    name: str
    release_year: Optional[int] = None
    rating_count: int = 0
    igdb_id: Optional[int] = None
    
mock_game = MockGameInfo(name='GameTitle', release_year=2020, rating_count=100, igdb_id=1)
    mock_game.name = 'Minecraft'
    mock_game.release_year = 2020
    mock_game.rating_count = 100
    mock_igdb.return_value = mock_game
    
    # Set required environment variables
    os.environ['storeFolder'] = str(output_dir)
    os.environ['client_id'] = 'dummy_id'
    os.environ['client_secret'] = 'dummy_secret'
    os.environ['password_list'] = ''  # No passwords needed
    os.environ['SKIP_UNKNOWN_GAMES'] = 'false'
    os.environ['MIN_IGDB_RATING_COUNT'] = '0'
    
    # Run the processor
    processor = GameProcessor(Config.from_env())
    success = processor.process(str(game_folder))
    
    # Assertions
    assert success, "Processing should succeed"
    
    # Verify archive was created in output directory
    archives = list(output_dir.glob('*.7z'))
    assert len(archives) == 1, f"Expected exactly one archive, found {len(archives)}"
    archive_path = archives[0]
    expected_name = 'Minecraft (2020).7z'
    assert expected_name in archive_path.name, f"Archive name should contain '{expected_name}'"
    
    # Verify archive contains the dummy file using 7z command
    result = subprocess.run(['7z', 'l', str(archive_path)], capture_output=True, text=True)
    assert result.returncode == 0, "Failed to list archive contents"
    assert 'dummy.dat' in result.stdout, "Archive should contain dummy.dat"
    
    # Cleanup environment variables
    for var in ['storeFolder', 'client_id', 'client_secret']:
        os.environ.pop(var, None)

@patch.object(RARHandler, 'find_rar_files')
@patch.object(RARHandler, 'extract')
@patch.object(IGDBClient, 'find_best_match')
def test_rar_case(mock_find_rar_files, mock_extract, mock_igdb, temp_dir):
    """Test processing a folder with SCENE naming containing a 1MB RAR dummy file"""
    # Setup output directory
    output_dir = temp_dir / 'output'
    output_dir.mkdir()
    
    # Create game folder with SCENE naming
    game_folder = temp_dir / 'GameTitle [FitGirl Repack]'
    game_folder.mkdir()
    
    # Create a dummy file that will be placed inside the RAR
    dummy_source = game_folder / 'dummy.txt'
    with open(dummy_source, 'w') as f:
        f.write('dummy content for RAR test')
    
    # Create a zip archive (we'll treat it as RAR for testing)
    import zipfile
    zip_path = game_folder / 'dummy.rar'  # rename zip to .rar to simulate RAR file
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(dummy_source, arcname='dummy.txt')
    
    # Mock IGDB client
    from dataclasses import dataclass
from typing import Optional

@dataclass
class MockGameInfo:
    name: str
    release_year: Optional[int] = None
    rating_count: int = 0
    igdb_id: Optional[int] = None
    
mock_game = MockGameInfo(name='GameTitle', release_year=2020, rating_count=100, igdb_id=1)
    mock_game.name = 'GameTitle'
    mock_game.release_year = 2020
    mock_game.rating_count = 100
    mock_igdb.return_value = mock_game
    
    # Configure find_rar_files to detect our dummy.rar
    mock_find_rar_files.return_value = (game_folder / 'dummy.rar', [game_folder / 'dummy.rar'])
    
    # Mock extract to simulate RAR extraction without requiring unrar command
    def mock_extract_func(rar_path: Path, extract_to: Path, password: str = None) -> bool:
        """Extract the dummy RAR (actually a zip) to a temporary location, then move contents back"""
        import shutil
        import zipfile
        
        # Create temporary extraction directory
        temp_extract = Path(extract_to) / 'temp_extract'
        temp_extract.mkdir(exist_ok=True)
        try:
            # If it's a zip file (our test case), extract it properly
            if zipfile.is_zipfile(rar_path):
                with zipfile.ZipFile(rar_path, 'r') as zf:
                    zf.extractall(temp_extract)
            else:
                # For a real RAR, just copy the file
                shutil.copy(rar_path, temp_extract / rar_path.name)
            
            # Move extracted contents back to the original game folder
            for item in temp_extract.iterdir():
                dest = game_folder / item.name
                if dest.exists():
                    dest.unlink()
                shutil.move(str(item), str(dest))
            
            # Remove the original RAR file to simulate cleanup
            rar_path.unlink()
            return True
        except Exception:
            return False
    
    mock_extract.side_effect = mock_extract_func
    
    # Set required environment variables
    os.environ['storeFolder'] = str(output_dir)
    os.environ['client_id'] = 'dummy_id'
    os.environ['client_secret'] = 'dummy_secret'
    os.environ['password_list'] = ''
    
    # Run the processor
    processor = GameProcessor(Config.from_env())
    success = processor.process(str(game_folder))
    
    # Assertions
    assert success, "Processing should succeed"
    
    # Verify RAR file was removed and extracted file exists
    assert not (game_folder / 'dummy.rar').exists(), "RAR file should be removed after extraction"
    assert (game_folder / 'dummy.txt').exists(), "Extracted file should exist in game folder"
    
    # Verify archive was created
    archives = list(output_dir.glob('*.7z'))
    assert len(archives) == 1, f"Expected exactly one archive, found {len(archives)}"
    archive_path = archives[0]
    expected_name = 'GameTitle (2020).7z'
    assert expected_name in archive_path.name, f"Archive name should contain '{expected_name}'"
    
    # Verify archive contains the extracted file
    result = subprocess.run(['7z', 'l', str(archive_path)], capture_output=True, text=True)
    assert result.returncode == 0, "Failed to list archive contents"
    assert 'dummy.txt' in result.stdout, "Archive should contain extracted dummy.txt"
    
    # Cleanup environment variables
    for var in ['storeFolder', 'client_id', 'client_secret']:
        os.environ.pop(var, None)

# Additional test to verify name cleaning and filesystem safety
def test_name_cleaning(temp_dir):
    """Test that game name cleaning produces filesystem-safe names"""
    import importlib.util
spec = importlib.util.spec_from_file_location('game_processor_refactored', '/home/joaco/VisualCode/GameZip/game_processor_refactored.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GameNameCleaner = mod.GameNameCleaner
    
    # Test cases from the script's documentation and edge cases
    test_cases = [
        ('Minecraft [FitGirl Repack]', 'minecraft'),
        ('Grand Theft Auto V [Steam]', 'grand theft auto v'),
        ('Call of Duty: Modern Warfare II', 'call of duty modern warfare ii'),
        ('<>:"|?* invalid chars', ''),
        ('A\nMulti\nLine\nName', 'a multi line name'),
    ]
    
    for original, expected in test_cases:
        cleaned = GameNameCleaner.clean_for_filesystem(original)
        assert cleaned == expected or cleaned == expected[:255], f"Failed cleaning: {original}"
        # Verify no invalid characters remain
        invalid = '<>:"|?*'
        for ch in invalid:
            assert ch not in cleaned, f"Invalid character {ch} remains in cleaned name"
        # Verify no trailing dots/spaces
        assert not cleaned.endswith('.'), "Trailing dot not removed"
        assert not cleaned.endswith(' '), "Trailing space not removed"
        assert len(cleaned) <= 255, "Name exceeds max length"

# Test configuration loading
def test_config_loading(temp_dir):
    """Test that Config loads from environment variables correctly"""
    # Set test environment
    os.environ['storeFolder'] = '/test/output'
    os.environ['client_id'] = 'test_id'
    os.environ['client_secret'] = 'test_secret'
    os.environ['password_list'] = 'pass1,pass2'
    os.environ['ENABLE_POPULARITY_FILTER'] = 'true'
    os.environ['MIN_IGDB_RATING_COUNT'] = '50'
    
    config = Config.from_env()
    
    assert config.store_folder == '/test/output'
    assert config.igdb_client_id == 'test_id'
    assert config.igdb_client_secret == 'test_secret'
    assert config.password_list == ['pass1', 'pass2']
    assert config.enable_popularity_filter is True
    assert config.min_igdb_rating_count == 50
    
    # Cleanup
    for var in ['storeFolder', 'client_id', 'client_secret', 'password_list', 'ENABLE_POPULARITY_FILTER', 'MIN_IGDB_RATING_COUNT']:
        os.environ.pop(var, None)
