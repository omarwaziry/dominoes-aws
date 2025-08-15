import unittest
import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import DatabaseManager, save_game_session, update_game_session, save_game_move, update_player_stats
from app.models import Base, GameSession, GameMove, PlayerStats, RequestLog, SystemMetrics

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test database"""
        # Create in-memory SQLite database for testing
        self.test_db_url = 'sqlite:///:memory:'
        
        # Create test engine and session
        self.engine = create_engine(self.test_db_url)
        Base.metadata.create_all(self.engine)
        
        # Create session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Create database manager for testing
        self.db_manager = DatabaseManager()
        self.db_manager.engine = self.engine
        self.db_manager.SessionLocal = sessionmaker(bind=self.engine)

    def tearDown(self):
        """Clean up after tests"""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_game_session_creation(self):
        """Test creating a game session"""
        game_session = GameSession(
            id='test-game-123',
            player_session_id='player-456',
            winner='player',
            player_score=5,
            ai_score=3
        )
        
        self.session.add(game_session)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(GameSession).filter_by(id='test-game-123').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.player_session_id, 'player-456')
        self.assertEqual(retrieved.winner, 'player')
        self.assertEqual(retrieved.player_score, 5)
        self.assertEqual(retrieved.ai_score, 3)

    def test_game_session_to_dict(self):
        """Test game session dictionary conversion"""
        game_session = GameSession(
            id='test-game-123',
            player_session_id='player-456',
            winner='player'
        )
        
        result = game_session.to_dict()
        
        self.assertEqual(result['id'], 'test-game-123')
        self.assertEqual(result['player_session_id'], 'player-456')
        self.assertEqual(result['winner'], 'player')
        self.assertIn('created_at', result)

    def test_game_session_state_management(self):
        """Test game state JSON serialization"""
        game_session = GameSession(
            id='test-game-123',
            player_session_id='player-456'
        )
        
        test_state = {
            'current_player': 'player',
            'board': [{'left': 1, 'right': 2}],
            'game_over': False
        }
        
        game_session.set_game_state(test_state)
        self.session.add(game_session)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(GameSession).filter_by(id='test-game-123').first()
        retrieved_state = retrieved.get_game_state()
        
        self.assertEqual(retrieved_state['current_player'], 'player')
        self.assertEqual(len(retrieved_state['board']), 1)
        self.assertEqual(retrieved_state['board'][0]['left'], 1)

    def test_game_move_creation(self):
        """Test creating game moves"""
        # First create a game session
        game_session = GameSession(
            id='test-game-123',
            player_session_id='player-456'
        )
        self.session.add(game_session)
        self.session.commit()
        
        # Create a move
        move = GameMove(
            game_session_id='test-game-123',
            move_number=1,
            player_type='player',
            tile_left=1,
            tile_right=2,
            position='left'
        )
        
        self.session.add(move)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(GameMove).filter_by(game_session_id='test-game-123').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.move_number, 1)
        self.assertEqual(retrieved.player_type, 'player')
        self.assertEqual(retrieved.tile_left, 1)
        self.assertEqual(retrieved.tile_right, 2)

    def test_player_stats_creation(self):
        """Test creating and updating player statistics"""
        stats = PlayerStats(
            session_id='player-456',
            total_games=5,
            games_won=3,
            games_lost=2
        )
        
        self.session.add(stats)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(PlayerStats).filter_by(session_id='player-456').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.total_games, 5)
        self.assertEqual(retrieved.games_won, 3)

    def test_player_stats_update(self):
        """Test updating player statistics"""
        stats = PlayerStats(session_id='player-456')
        self.session.add(stats)
        self.session.commit()
        
        # Update stats
        stats.update_stats(game_won=True, move_count=15, duration_minutes=8.5)
        self.session.commit()
        
        # Verify updates
        self.assertEqual(stats.total_games, 1)
        self.assertEqual(stats.games_won, 1)
        self.assertEqual(stats.games_lost, 0)
        self.assertEqual(stats.total_moves, 15)
        self.assertEqual(stats.average_game_duration, 8.5)

    def test_player_stats_to_dict(self):
        """Test player stats dictionary conversion"""
        stats = PlayerStats(
            session_id='player-456',
            total_games=10,
            games_won=6,
            games_lost=4
        )
        
        result = stats.to_dict()
        
        self.assertEqual(result['session_id'], 'player-456')
        self.assertEqual(result['total_games'], 10)
        self.assertEqual(result['games_won'], 6)
        self.assertEqual(result['win_rate'], 60.0)

    def test_request_log_creation(self):
        """Test creating request logs"""
        log_entry = RequestLog(
            method='GET',
            endpoint='/api/new-game',
            status_code=200,
            response_time_ms=150,
            user_agent='Test Agent',
            ip_address='127.0.0.1'
        )
        
        self.session.add(log_entry)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(RequestLog).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.method, 'GET')
        self.assertEqual(retrieved.endpoint, '/api/new-game')
        self.assertEqual(retrieved.status_code, 200)

    def test_system_metrics_creation(self):
        """Test creating system metrics"""
        metric = SystemMetrics(
            metric_name='cpu_usage',
            metric_value=75.5,
            metric_unit='percent'
        )
        
        tags = {'instance': 'web-1', 'region': 'us-east-1'}
        metric.set_tags(tags)
        
        self.session.add(metric)
        self.session.commit()
        
        # Retrieve and verify
        retrieved = self.session.query(SystemMetrics).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.metric_name, 'cpu_usage')
        self.assertEqual(retrieved.metric_value, 75.5)
        
        retrieved_tags = retrieved.get_tags()
        self.assertEqual(retrieved_tags['instance'], 'web-1')

    def test_database_manager_health_check(self):
        """Test database manager health check"""
        # Mock the database manager with our test setup
        self.db_manager.engine = self.engine
        self.db_manager.SessionLocal = sessionmaker(bind=self.engine)
        
        healthy, message = self.db_manager.health_check()
        
        self.assertTrue(healthy)
        self.assertEqual(message, "Database connection healthy")

    def test_relationships(self):
        """Test model relationships"""
        # Create game session
        game_session = GameSession(
            id='test-game-123',
            player_session_id='player-456'
        )
        self.session.add(game_session)
        self.session.commit()
        
        # Create moves
        move1 = GameMove(
            game_session_id='test-game-123',
            move_number=1,
            player_type='player',
            tile_left=1,
            tile_right=2,
            position='left'
        )
        
        move2 = GameMove(
            game_session_id='test-game-123',
            move_number=2,
            player_type='ai',
            tile_left=2,
            tile_right=3,
            position='right'
        )
        
        self.session.add_all([move1, move2])
        self.session.commit()
        
        # Test relationship
        retrieved_session = self.session.query(GameSession).filter_by(id='test-game-123').first()
        self.assertEqual(len(retrieved_session.moves), 2)
        self.assertEqual(retrieved_session.moves[0].player_type, 'player')
        self.assertEqual(retrieved_session.moves[1].player_type, 'ai')

if __name__ == '__main__':
    unittest.main()