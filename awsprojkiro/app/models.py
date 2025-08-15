"""
Database models for the dominoes application using SQLAlchemy ORM.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import json

Base = declarative_base()

class GameSession(Base):
    """Model for storing game session information"""
    __tablename__ = 'game_sessions'
    
    id = Column(String(36), primary_key=True)  # UUID
    player_session_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    winner = Column(String(10), nullable=True)  # 'player' or 'ai'
    player_score = Column(Integer, default=0)
    ai_score = Column(Integer, default=0)
    game_state = Column(Text, nullable=True)  # JSON string of game state
    is_active = Column(Boolean, default=True)
    
    # Relationships
    moves = relationship("GameMove", back_populates="game_session", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'player_session_id': self.player_session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'winner': self.winner,
            'player_score': self.player_score,
            'ai_score': self.ai_score,
            'is_active': self.is_active,
            'move_count': len(self.moves) if self.moves else 0
        }
    
    def set_game_state(self, state_dict):
        """Set game state as JSON string"""
        self.game_state = json.dumps(state_dict)
    
    def get_game_state(self):
        """Get game state as dictionary"""
        if self.game_state:
            return json.loads(self.game_state)
        return None

class GameMove(Base):
    """Model for storing individual game moves"""
    __tablename__ = 'game_moves'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_session_id = Column(String(36), ForeignKey('game_sessions.id'), nullable=False)
    move_number = Column(Integer, nullable=False)
    player_type = Column(String(10), nullable=False)  # 'player' or 'ai'
    tile_left = Column(Integer, nullable=False)
    tile_right = Column(Integer, nullable=False)
    position = Column(String(10), nullable=False)  # 'left', 'right', or 'center'
    timestamp = Column(DateTime, default=datetime.utcnow)
    board_state_before = Column(Text, nullable=True)  # JSON string
    board_state_after = Column(Text, nullable=True)   # JSON string
    
    # Relationships
    game_session = relationship("GameSession", back_populates="moves")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'game_session_id': self.game_session_id,
            'move_number': self.move_number,
            'player_type': self.player_type,
            'tile': {'left': self.tile_left, 'right': self.tile_right},
            'position': self.position,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class PlayerStats(Base):
    """Model for storing player statistics"""
    __tablename__ = 'player_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    total_games = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    games_lost = Column(Integer, default=0)
    total_moves = Column(Integer, default=0)
    average_game_duration = Column(Float, default=0.0)  # in minutes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        win_rate = (self.games_won / self.total_games * 100) if self.total_games > 0 else 0
        return {
            'session_id': self.session_id,
            'total_games': self.total_games,
            'games_won': self.games_won,
            'games_lost': self.games_lost,
            'win_rate': round(win_rate, 2),
            'total_moves': self.total_moves,
            'average_game_duration': round(self.average_game_duration, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_stats(self, game_won, move_count, duration_minutes):
        """Update player statistics after a game"""
        self.total_games += 1
        if game_won:
            self.games_won += 1
        else:
            self.games_lost += 1
        
        self.total_moves += move_count
        
        # Update average duration
        if self.total_games == 1:
            self.average_game_duration = duration_minutes
        else:
            total_duration = self.average_game_duration * (self.total_games - 1) + duration_minutes
            self.average_game_duration = total_duration / self.total_games
        
        self.updated_at = datetime.utcnow()

class RequestLog(Base):
    """Model for logging HTTP requests for analytics"""
    __tablename__ = 'request_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    method = Column(String(10), nullable=False)
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    session_id = Column(String(255), nullable=True)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'method': self.method,
            'endpoint': self.endpoint,
            'status_code': self.status_code,
            'response_time_ms': self.response_time_ms,
            'user_agent': self.user_agent,
            'ip_address': self.ip_address,
            'session_id': self.session_id
        }

class SystemMetrics(Base):
    """Model for storing custom application metrics"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    tags = Column(Text, nullable=True)  # JSON string for additional metadata
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'metric_unit': self.metric_unit,
            'tags': json.loads(self.tags) if self.tags else None
        }
    
    def set_tags(self, tags_dict):
        """Set tags as JSON string"""
        self.tags = json.dumps(tags_dict)
    
    def get_tags(self):
        """Get tags as dictionary"""
        if self.tags:
            return json.loads(self.tags)
        return {}