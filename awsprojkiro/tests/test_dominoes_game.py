import unittest
from app.dominoes_game import DominoesGame, Tile

class TestTile(unittest.TestCase):
    def test_tile_creation(self):
        """Test tile creation and basic properties"""
        tile = Tile(1, 2)
        self.assertEqual(tile.left, 1)
        self.assertEqual(tile.right, 2)

    def test_tile_equality(self):
        """Test tile equality comparison"""
        tile1 = Tile(1, 2)
        tile2 = Tile(2, 1)  # Should be equal (flipped)
        tile3 = Tile(1, 3)  # Should not be equal
        
        self.assertEqual(tile1, tile2)
        self.assertNotEqual(tile1, tile3)

    def test_is_double(self):
        """Test double tile detection"""
        double_tile = Tile(3, 3)
        regular_tile = Tile(1, 2)
        
        self.assertTrue(double_tile.is_double())
        self.assertFalse(regular_tile.is_double())

    def test_has_value(self):
        """Test value checking"""
        tile = Tile(1, 4)
        
        self.assertTrue(tile.has_value(1))
        self.assertTrue(tile.has_value(4))
        self.assertFalse(tile.has_value(2))

    def test_get_other_value(self):
        """Test getting the other value"""
        tile = Tile(2, 5)
        
        self.assertEqual(tile.get_other_value(2), 5)
        self.assertEqual(tile.get_other_value(5), 2)
        self.assertIsNone(tile.get_other_value(3))

    def test_to_dict(self):
        """Test dictionary conversion"""
        tile = Tile(3, 6)
        expected = {'left': 3, 'right': 6}
        
        self.assertEqual(tile.to_dict(), expected)

class TestDominoesGame(unittest.TestCase):
    def setUp(self):
        """Set up a new game for each test"""
        self.game = DominoesGame()

    def test_game_initialization(self):
        """Test game initialization"""
        # Check that hands are dealt correctly (AI may have played opening tile)
        self.assertEqual(len(self.game.player_hand), 7)
        # AI hand may be 6 or 7 depending on who starts
        self.assertIn(len(self.game.ai_hand), [6, 7])
        # Total tiles should be 28
        total_tiles = len(self.game.player_hand) + len(self.game.ai_hand) + len(self.game.boneyard) + len(self.game.board)
        self.assertEqual(total_tiles, 28)
        
        # Check that game state is initialized
        self.assertFalse(self.game.game_over)
        self.assertIsNone(self.game.winner)
        self.assertIn(self.game.current_player, ['player', 'ai'])

    def test_domino_set_creation(self):
        """Test that a complete domino set is created"""
        tiles = self.game._create_domino_set()
        self.assertEqual(len(tiles), 28)  # Standard double-six set
        
        # Check that all combinations exist
        expected_tiles = []
        for i in range(7):
            for j in range(i, 7):
                expected_tiles.append((i, j))
        
        actual_tiles = [(t.left, t.right) for t in tiles]
        for expected in expected_tiles:
            self.assertIn(expected, actual_tiles)

    def test_board_ends(self):
        """Test board end detection"""
        # Create fresh game for testing
        fresh_game = DominoesGame()
        fresh_game.board = []  # Force empty board
        
        # Empty board
        left, right = fresh_game.get_board_ends()
        self.assertIsNone(left)
        self.assertIsNone(right)
        
        # Add tiles to board
        fresh_game.board = [Tile(1, 2), Tile(2, 3), Tile(3, 4)]
        left, right = fresh_game.get_board_ends()
        self.assertEqual(left, 1)
        self.assertEqual(right, 4)

    def test_can_play_tile(self):
        """Test tile playability checking"""
        # Create a fresh game with empty board for testing
        fresh_game = DominoesGame()
        fresh_game.board = []  # Force empty board
        
        # Empty board - any tile can be played
        tile = Tile(1, 2)
        playable = fresh_game.can_play_tile(tile)
        self.assertTrue(playable['left'])
        self.assertTrue(playable['right'])
        
        # Board with tiles - manually set board ends
        fresh_game.board = [Tile(1, 2), Tile(2, 3)]  # Left end is 1, right end is 3
        
        # Tile that can play on left (has value 1)
        tile_left = Tile(1, 4)
        playable = fresh_game.can_play_tile(tile_left)
        self.assertTrue(playable['left'])
        self.assertFalse(playable['right'])
        
        # Tile that can play on right
        tile_right = Tile(3, 5)
        playable = fresh_game.can_play_tile(tile_right)
        self.assertFalse(playable['left'])
        self.assertTrue(playable['right'])
        
        # Tile that can play on both sides
        tile_both = Tile(1, 3)
        playable = fresh_game.can_play_tile(tile_both)
        self.assertTrue(playable['left'])
        self.assertTrue(playable['right'])
        
        # Tile that cannot be played
        tile_none = Tile(4, 5)
        playable = fresh_game.can_play_tile(tile_none)
        self.assertFalse(playable['left'])
        self.assertFalse(playable['right'])

    def test_game_state(self):
        """Test game state retrieval"""
        state = self.game.get_game_state()
        
        self.assertIn('current_player', state)
        self.assertIn('game_over', state)
        self.assertIn('winner', state)
        self.assertIn('player_tile_count', state)
        self.assertIn('ai_tile_count', state)
        self.assertIn('boneyard_count', state)
        self.assertIn('board_ends', state)
        self.assertIn('player_can_play', state)
        
        # Check initial values
        self.assertEqual(state['player_tile_count'], 7)
        # AI tile count may be 6 or 7 depending on who starts
        self.assertIn(state['ai_tile_count'], [6, 7])
        # Boneyard count depends on whether AI played opening tile
        self.assertIn(state['boneyard_count'], [13, 14])
        self.assertFalse(state['game_over'])

    def test_player_hand_serialization(self):
        """Test player hand serialization"""
        hand = self.game.get_player_hand()
        
        self.assertEqual(len(hand), 7)
        for tile_dict in hand:
            self.assertIn('left', tile_dict)
            self.assertIn('right', tile_dict)
            self.assertIsInstance(tile_dict['left'], int)
            self.assertIsInstance(tile_dict['right'], int)

    def test_board_serialization(self):
        """Test board serialization"""
        # Empty board
        board = self.game.get_board()
        self.assertEqual(len(board), 0)
        
        # Add tiles to board
        self.game.board = [Tile(1, 2), Tile(2, 3)]
        board = self.game.get_board()
        
        self.assertEqual(len(board), 2)
        for tile_dict in board:
            self.assertIn('left', tile_dict)
            self.assertIn('right', tile_dict)

    def test_tile_value_calculation(self):
        """Test tile value calculation for AI strategy"""
        tile1 = Tile(1, 2)  # Value = 3
        tile2 = Tile(4, 6)  # Value = 10
        tile3 = Tile(0, 0)  # Value = 0
        
        self.assertEqual(self.game._tile_value(tile1), 3)
        self.assertEqual(self.game._tile_value(tile2), 10)
        self.assertEqual(self.game._tile_value(tile3), 0)

if __name__ == '__main__':
    unittest.main()