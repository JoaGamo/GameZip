# Test cases for main.py

import os
import shutil
import tempfile
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Import the components to test from main.py
import importlib.util, sys
spec = importlib.util.spec_from_file_location('main', '/home/joaco/VisualCode/GameZip/main.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GameProcessor = mod.GameProcessor
Config = mod.Config
IGDBClient = mod.IGDBClient
RARHandler = mod.RARHandler
GameNameCleaner = mod.GameNameCleaner
ProcessResult = mod.ProcessResult


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    d = Path(tempfile.mkdtemp(prefix='game_processor_test_'))
    yield d
    shutil.rmtree(d)

def create_dummy_file(path: Path, size_mb: int = 1) -> Path:
    """Create a dummy file of specified size in MB"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x00' * (size_mb * 1024 * 1024))
    return path

@patch('main.IGDBClient.find_best_match')
def test_plain_file_case(mock_igdb, temp_dir):
    """Test processing a folder with SCENE naming containing a 1MB dummy file (no RAR)"""
    output_dir = temp_dir / 'output'
    output_dir.mkdir()

    game_folder = temp_dir / 'Minecraft [FitGirl Repack]'
    dummy_file = create_dummy_file(game_folder / 'dummy.dat')

    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class MockGameInfo:
        name: str
        release_year: Optional[int] = None
        rating_count: int = 0
        igdb_id: Optional[int] = None
        cover_url: Optional[str] = None

    mock_game = MockGameInfo(name='Minecraft', release_year=2020, rating_count=100, igdb_id=1)
    mock_igdb.return_value = mock_game

    os.environ['storeFolder'] = str(output_dir)
    os.environ['client_id'] = 'dummy_id'
    os.environ['client_secret'] = 'dummy_secret'
    os.environ['password_list'] = ''
    os.environ['SKIP_UNKNOWN_GAMES'] = 'false'
    os.environ['MIN_IGDB_RATING_COUNT'] = '0'

    processor = GameProcessor(Config.from_env())
    result = processor.process(str(game_folder))

    assert result, "Processing should succeed"
    archives = list(output_dir.glob('*.7z'))
    assert len(archives) == 1, f"Expected exactly one archive, found {len(archives)}"
    archive_path = archives[0]
    assert 'Minecraft' in archive_path.name and '2020' in archive_path.name

    for var in ['storeFolder', 'client_id', 'client_secret']:
        os.environ.pop(var, None)

@patch('main.IGDBClient.find_best_match')
def test_rar_case(mock_igdb, temp_dir):
    """Test processing a folder with SCENE naming containing a 1MB RAR dummy file"""
    output_dir = temp_dir / 'output'
    output_dir.mkdir()

    game_folder = temp_dir / 'GameTitle [FitGirl Repack]'
    game_folder.mkdir()

    dummy_source = game_folder / 'dummy.txt'
    with open(dummy_source, 'w') as f:
        f.write('dummy content for RAR test')

    import zipfile
    zip_path = game_folder / 'dummy.rar'
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(dummy_source, arcname='dummy.txt')

    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class MockGameInfo:
        name: str
        release_year: Optional[int] = None
        rating_count: int = 0
        igdb_id: Optional[int] = None
        cover_url: Optional[str] = None

    mock_game = MockGameInfo(name='GameTitle', release_year=2020, rating_count=100, igdb_id=1)
    mock_igdb.return_value = mock_game

    os.environ['storeFolder'] = str(output_dir)
    os.environ['client_id'] = 'dummy_id'
    os.environ['client_secret'] = 'dummy_secret'
    os.environ['password_list'] = ''

    # Patch process_rar_archive to simulate successful extraction without real RAR
    from main import GameProcessor, Config
    processor = GameProcessor(Config.from_env())

    original_process_rar = processor.rar_handler.process_rar_archive
    def mock_process_rar(folder_path):
        return True, game_folder
    processor.rar_handler.process_rar_archive = mock_process_rar

    result = processor.process(str(game_folder))

    assert result, "Processing should succeed"
    archives = list(output_dir.glob('*.7z'))
    assert len(archives) == 1, f"Expected exactly one archive, found {len(archives)}"
    archive_path = archives[0]
    assert 'GameTitle' in archive_path.name and '2020' in archive_path.name

    for var in ['storeFolder', 'client_id', 'client_secret']:
        os.environ.pop(var, None)

def test_name_cleaning(temp_dir):
    """Test that game name cleaning produces filesystem-safe names"""
    test_cases = [
        ('Minecraft [FitGirl Repack]', 'Minecraft [FitGirl Repack]'),
        ('Grand Theft Auto V [Steam]', 'Grand Theft Auto V [Steam]'),
        ('Call of Duty: Modern Warfare II', 'Call of Duty Modern Warfare II'),
        ('<>:"|?* invalid chars', ' invalid chars'),
        ('trailing..  ', 'trailing'),
    ]
    for original, expected in test_cases:
        cleaned = GameNameCleaner.clean_for_filesystem(original)
        assert cleaned == expected or cleaned == expected[:255], f"Failed cleaning: {original!r} -> {cleaned!r}"
        invalid = '<>:"|?*'
        for ch in invalid:
            assert ch not in cleaned, f"Invalid character {ch} remains in cleaned name"
        assert not cleaned.endswith('.'), "Trailing dot not removed"
        assert not cleaned.endswith(' '), "Trailing space not removed"
        assert len(cleaned) <= 255, "Name exceeds max length"

def test_config_loading(temp_dir):
    """Test that Config loads from environment variables correctly"""
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

    for var in ['storeFolder', 'client_id', 'client_secret', 'password_list', 'ENABLE_POPULARITY_FILTER', 'MIN_IGDB_RATING_COUNT']:
        os.environ.pop(var, None)

def test_process_result_truthiness():
    """ProcessResult(1) should be truthy; ProcessResult(0) should be falsy"""
    success = ProcessResult(1, game_name='Test', archive_path=Path('/tmp/x.7z'), cover_url=None)
    failure = ProcessResult(0)
    assert success
    assert not failure
    assert success.game_name == 'Test'
    assert success.archive_path == Path('/tmp/x.7z')