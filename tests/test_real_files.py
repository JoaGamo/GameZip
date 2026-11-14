# Real file integration tests for game_processor_refactored.py

import os
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Import the actual module
import importlib.util
spec = importlib.util.spec_from_file_location('game_processor_refactored', '/home/joaco/VisualCode/GameZip/game_processor_refactored.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GameProcessor = mod.GameProcessor
Config = mod.Config
RARHandler = mod.RARHandler

class RealFileTests(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp(prefix='game_real_test_'))
        self.output_dir = self.test_dir / 'output'
        self.output_dir.mkdir()
        
        # Set environment variables
        os.environ['storeFolder'] = str(self.output_dir)
        os.environ['client_id'] = 'dummy_id'
        os.environ['client_secret'] = 'dummy_secret'
        os.environ['password_list'] = ''
        os.environ['SKIP_UNKNOWN_GAMES'] = 'false'
        os.environ['MIN_IGDB_RATING_COUNT'] = '0'
        
    def tearDown(self):
        """Clean up environment variables"""
        for var in ['storeFolder', 'client_id', 'client_secret', 'password_list', 'SKIP_UNKNOWN_GAMES', 'MIN_IGDB_RATING_COUNT']:
            os.environ.pop(var, None)
        shutil.rmtree(self.test_dir)
    
    def create_1mb_file(self, path: Path) -> Path:
        """Create a real 1MB file using random data"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(os.urandom(1024 * 1024))
        return path
    
    def test_real_1mb_file_case(self):
        """Test with real 1MB file and SCENE naming"""
        # Create game folder with SCENE naming
        game_folder = self.test_dir / 'Minecraft [FitGirl Repack]'
        self.create_1mb_file(game_folder / 'dummy.dat')
        
        # Run processor with mocked IGDB client
        processor = GameProcessor(Config.from_env())
        processor.igdb_client = MagicMock()
        mock_game = MagicMock()
        mock_game.name = 'Minecraft'
        mock_game.release_year = 2020
        mock_game.rating_count = 100
        processor.igdb_client.find_best_match.return_value = mock_game
        
        success = processor.process(str(game_folder))
        self.assertTrue(success, "Processing should succeed")
        
        # Verify archive created
        archives = list(self.output_dir.glob('*.7z'))
        self.assertEqual(len(archives), 1, f"Expected 1 archive, found {len(archives)}")
        archive_path = archives[0]
        expected_name = 'Minecraft (2020).7z'
        self.assertIn(expected_name, archive_path.name)
        
        # Verify content using 7z
        result = subprocess.run(['7z', 'l', str(archive_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('dummy.dat', result.stdout)
    
    def test_real_rar_case(self):
        """Test with real RAR file and SCENE naming"""
        # Create game folder
        game_folder = self.test_dir / 'GameTitle [FitGirl Rep2]'
        game_folder.mkdir()
        
        # Create dummy file to be inside RAR
        dummy_source = game_folder / 'dummy.txt'
        with open(dummy_source, 'w') as f:
            f.write('Real RAR test content')
        
        # Create real RAR file using unrar if available
        rar_path = game_folder / 'dummy.rar'
        try:
            subprocess.run(['unrar', 'a', '-y', str(rar_path), str(dummy_source)], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("unrar command not available - cannot create real RAR files")
        
        # Mock IGDB find_rar_files to detect our real RAR
        original_find = RARHandler.find_rar_files
        try:
            def mock_find(folder_path):
                if folder_path == game_folder:
                    return (rar_path, [rar_path])
                return original_find(folder_path)
            
            RARHandler.find_rar_files = mock_find
            
            # Run processor
            processor = GameProcessor(Config.from_env())
            processor.igdb_client = MagicMock()
            mock_game = MagicMock()
            mock_game.name = 'GameTitle'
            mock_game.release_year = 2020
            mock_game.rating_count = 100
            processor.igdb_client.find_best_match.return_value = mock_game
            
            success = processor.process(str(game_folder))
            self.assertTrue(success, "Processing should succeed")
            
            # Verify RAR extracted and removed
            self.assertFalse(rar_path.exists(), "RAR file should be removed after extraction")
            self.assertTrue((game_folder / 'dummy.txt').exists(), "Extracted file should exist")
            
            # Verify archive created
            archives = list(self.output_dir.glob('*.7z'))
            self.assertEqual(len(archives), 1)
            archive_path = archives[0]
            expected_name = 'GameTitle (2020).7z'
            self.assertIn(expected_name, archive_path.name)
            
            # Verify archive contains extracted file
            result = subprocess.run(['7z', 'l', str(archive_path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn('dummy.txt', result.stdout)
        finally:
            RARHandler.find_rar_files = original_find

if __name__ == '__main__':
    unittest.main()