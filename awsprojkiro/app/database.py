"""
Database connection and session management for the dominoes application.
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
import time
import json
import boto3
from botocore.exceptions import ClientError

from app.models import Base

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self, app=None):
        self.engine = None
        self.SessionLocal = None
        self.app = app
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize database with Flask app"""
        self.app = app
        
        # Get database URL from config or environment
        database_url = app.config.get('DATABASE_URL') or os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.warning("No DATABASE_URL configured. Database features will be disabled.")
            return
        
        # Handle AWS Secrets Manager for RDS credentials
        if database_url.startswith('secrets-manager://'):
            database_url = self._get_database_url_from_secrets(database_url)
        
        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
            echo=app.config.get('SQLALCHEMY_ECHO', False)
        )
        
        # Add connection event listeners
        event.listen(self.engine, 'connect', self._on_connect)
        event.listen(self.engine, 'checkout', self._on_checkout)
        
        # Create session factory
        self.SessionLocal = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )
        
        # Create tables
        self.create_tables()
        
        # Store in app for easy access
        app.db = self
    
    def _get_database_url_from_secrets(self, secrets_url):
        """Get database URL from AWS Secrets Manager"""
        try:
            # Parse secrets manager URL: secrets-manager://secret-name/region
            parts = secrets_url.replace('secrets-manager://', '').split('/')
            secret_name = parts[0]
            region = parts[1] if len(parts) > 1 else 'us-east-1'
            
            # Get secret from AWS Secrets Manager
            session = boto3.session.Session()
            client = session.client('secretsmanager', region_name=region)
            
            response = client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response['SecretString'])
            
            # Build database URL
            username = secret['username']
            password = secret['password']
            host = secret['host']
            port = secret.get('port', 3306)
            dbname = secret.get('dbname', 'dominoesdb')
            
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{dbname}"
            
        except ClientError as e:
            logger.error(f"Failed to get database credentials from Secrets Manager: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing secrets manager URL: {e}")
            raise
    
    def _on_connect(self, dbapi_connection, connection_record):
        """Called when a new database connection is created"""
        logger.debug("New database connection established")
    
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """Called when a connection is checked out from the pool"""
        logger.debug("Database connection checked out from pool")
    
    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def get_session(self):
        """Get a database session"""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            session.close()
    
    def health_check(self):
        """Check database connectivity"""
        if not self.engine:
            return False, "Database not configured"
        
        try:
            with self.session_scope() as session:
                session.execute('SELECT 1')
            return True, "Database connection healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False, f"Database connection failed: {str(e)}"
    
    def get_connection_info(self):
        """Get database connection information"""
        if not self.engine:
            return None
        
        try:
            pool = self.engine.pool
            return {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid()
            }
        except Exception as e:
            logger.error(f"Failed to get connection info: {e}")
            return None

# Global database manager instance
db_manager = DatabaseManager()

def init_database(app):
    """Initialize database with Flask app"""
    db_manager.init_app(app)
    return db_manager

# Utility functions for common database operations
def save_game_session(game_id, player_session_id, game_state=None):
    """Save a new game session to database"""
    try:
        from app.models import GameSession
        
        with db_manager.session_scope() as session:
            game_session = GameSession(
                id=game_id,
                player_session_id=player_session_id
            )
            
            if game_state:
                game_session.set_game_state(game_state)
            
            session.add(game_session)
            return game_session.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to save game session: {e}")
        return None

def update_game_session(game_id, winner=None, game_state=None, completed=False):
    """Update an existing game session"""
    try:
        from app.models import GameSession
        from datetime import datetime
        
        with db_manager.session_scope() as session:
            game_session = session.query(GameSession).filter_by(id=game_id).first()
            
            if not game_session:
                return None
            
            if winner:
                game_session.winner = winner
            
            if game_state:
                game_session.set_game_state(game_state)
            
            if completed:
                game_session.completed_at = datetime.utcnow()
                game_session.is_active = False
            
            return game_session.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to update game session: {e}")
        return None

def save_game_move(game_id, move_number, player_type, tile, position, board_before=None, board_after=None):
    """Save a game move to database"""
    try:
        from app.models import GameMove
        
        with db_manager.session_scope() as session:
            move = GameMove(
                game_session_id=game_id,
                move_number=move_number,
                player_type=player_type,
                tile_left=tile['left'],
                tile_right=tile['right'],
                position=position
            )
            
            if board_before:
                move.board_state_before = json.dumps(board_before)
            
            if board_after:
                move.board_state_after = json.dumps(board_after)
            
            session.add(move)
            return move.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to save game move: {e}")
        return None

def update_player_stats(session_id, game_won, move_count, duration_minutes):
    """Update player statistics"""
    try:
        from app.models import PlayerStats
        
        with db_manager.session_scope() as session:
            stats = session.query(PlayerStats).filter_by(session_id=session_id).first()
            
            if not stats:
                stats = PlayerStats(session_id=session_id)
                session.add(stats)
            
            stats.update_stats(game_won, move_count, duration_minutes)
            return stats.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to update player stats: {e}")
        return None

def log_request(method, endpoint, status_code, response_time_ms, user_agent=None, ip_address=None, session_id=None):
    """Log HTTP request for analytics"""
    try:
        from app.models import RequestLog
        
        with db_manager.session_scope() as session:
            log_entry = RequestLog(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_agent=user_agent,
                ip_address=ip_address,
                session_id=session_id
            )
            
            session.add(log_entry)
            return log_entry.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to log request: {e}")
        return None

def save_metric(metric_name, metric_value, metric_unit=None, tags=None):
    """Save custom application metric"""
    try:
        from app.models import SystemMetrics
        
        with db_manager.session_scope() as session:
            metric = SystemMetrics(
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit
            )
            
            if tags:
                metric.set_tags(tags)
            
            session.add(metric)
            return metric.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to save metric: {e}")
        return None