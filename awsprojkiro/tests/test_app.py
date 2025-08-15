import unittest
import json
from app.main import create_app

class TestDominoesApp(unittest.TestCase):
    def setUp(self):
        """Set up test client"""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        """Clean up after tests"""
        self.app_context.pop()

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
        self.assertIn('active_games', data)

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('games', data)
        self.assertIn('active_games', data['games'])
        self.assertIn('memory_usage_percent', data['games'])
        self.assertIn('system', data)
        self.assertIn('config_name', data['system'])

    def test_main_endpoint(self):
        """Test main application endpoint"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dominoes Game', response.data)

    def test_new_game_endpoint(self):
        """Test new game creation"""
        with self.client.session_transaction() as sess:
            # Initialize session
            pass
            
        response = self.client.post('/api/new-game',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('game_id', data)
        self.assertIn('player_hand', data)
        self.assertIn('board', data)
        self.assertIn('game_state', data)
        
        # Check that player has 7 tiles
        self.assertEqual(len(data['player_hand']), 7)

    def test_session_score_endpoint(self):
        """Test session score retrieval"""
        with self.client.session_transaction() as sess:
            sess['player_wins'] = 5
            sess['ai_wins'] = 3
            
        response = self.client.get('/api/session-score')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['player_wins'], 5)
        self.assertEqual(data['ai_wins'], 3)

    def test_reset_score_endpoint(self):
        """Test session score reset"""
        with self.client.session_transaction() as sess:
            sess['player_wins'] = 5
            sess['ai_wins'] = 3
            
        response = self.client.post('/api/reset-score',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['player_wins'], 0)
        self.assertEqual(data['ai_wins'], 0)

    def test_play_tile_without_game(self):
        """Test playing tile without active game"""
        response = self.client.post('/api/play-tile',
                                  data=json.dumps({
                                      'tile': {'left': 1, 'right': 2},
                                      'position': 'left'
                                  }),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_draw_tile_without_game(self):
        """Test drawing tile without active game"""
        response = self.client.post('/api/draw-tile',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()