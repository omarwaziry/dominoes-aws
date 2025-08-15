from flask import Flask, render_template, request, jsonify, session
import uuid
import os
import logging
from datetime import datetime
from app.dominoes_game import DominoesGame
from app.config import config
from app.monitoring import setup_monitoring, monitor, monitor_endpoint
from app.middleware import RequestLoggingMiddleware, ErrorHandlingMiddleware
from app.database import init_database, db_manager, save_game_session, update_game_session, save_game_move, update_player_stats
from app.cost_optimizer import FreeTierMonitor

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config[config_name])
    
    # Set up logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    
    # Set up monitoring middleware
    setup_monitoring(app)
    
    # Set up request logging and error handling
    RequestLoggingMiddleware(app)
    ErrorHandlingMiddleware(app)
    
    # Initialize database
    init_database(app)
    
    # Store active games in memory (use Redis/database for production)
    app.games = {}
    
    # Health check endpoint for ALB
    @app.route('/health')
    @monitor_endpoint
    def health_check():
        """Health check endpoint for AWS Application Load Balancer"""
        try:
            # Record health check
            monitor.record_health_check()
            
            # Check application health
            is_healthy, health_message = monitor.is_healthy()
            
            # Check database health if configured
            db_healthy = True
            db_message = "Database not configured"
            if db_manager.engine:
                db_healthy, db_message = db_manager.health_check()
            
            overall_healthy = is_healthy and db_healthy
            
            health_status = {
                'status': 'healthy' if overall_healthy else 'degraded',
                'message': health_message,
                'database': {
                    'status': 'healthy' if db_healthy else 'unhealthy',
                    'message': db_message
                },
                'timestamp': datetime.utcnow().isoformat(),
                'active_games': len(app.games),
                'config': config_name,
                'version': '1.0.0'
            }
            
            # Check if we're approaching memory limits
            if len(app.games) > app.config['MAX_GAMES_IN_MEMORY'] * 0.9:
                health_status['warning'] = 'Approaching maximum games limit'
                health_status['games_limit_usage'] = (len(app.games) / app.config['MAX_GAMES_IN_MEMORY']) * 100
            
            # Additional health checks
            health_status['checks'] = {
                'memory_usage': f"{(len(app.games) / app.config['MAX_GAMES_IN_MEMORY']) * 100:.1f}%",
                'games_active': len(app.games),
                'games_limit': app.config['MAX_GAMES_IN_MEMORY']
            }
            
            status_code = 200 if overall_healthy else 503
            return jsonify(health_status), status_code
            
        except Exception as e:
            app.logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 503
    
    # Metrics endpoint for CloudWatch monitoring
    @app.route('/metrics')
    @monitor_endpoint
    def metrics():
        """Comprehensive metrics endpoint for monitoring"""
        try:
            # Get application metrics from monitor
            app_metrics = monitor.get_metrics()
            
            # Add game-specific metrics
            game_metrics = {
                'active_games': len(app.games),
                'memory_usage_percent': (len(app.games) / app.config['MAX_GAMES_IN_MEMORY']) * 100,
                'games_limit': app.config['MAX_GAMES_IN_MEMORY']
            }
            
            # Combine all metrics
            metrics_data = {
                'application': app_metrics,
                'games': game_metrics,
                'system': {
                    'config_name': config_name,
                    'debug_mode': app.config['DEBUG'],
                    'flask_env': os.environ.get('FLASK_ENV', 'production')
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return jsonify(metrics_data), 200
        except Exception as e:
            app.logger.error(f"Metrics collection failed: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/new-game', methods=['POST'])
    def new_game():
        # Initialize session scores if not exists
        if 'player_wins' not in session:
            session['player_wins'] = 0
        if 'ai_wins' not in session:
            session['ai_wins'] = 0
        
        game_id = str(uuid.uuid4())
        game = DominoesGame()
        
        # Clean up old games if approaching memory limit
        if len(app.games) >= app.config['MAX_GAMES_IN_MEMORY']:
            # Remove oldest games (simple cleanup strategy)
            old_games = list(app.games.keys())[:-app.config['MAX_GAMES_IN_MEMORY']//2]
            for old_game_id in old_games:
                del app.games[old_game_id]
        
        app.games[game_id] = game
        session['game_id'] = game_id
        
        # Save game session to database if available
        if db_manager.engine:
            try:
                save_game_session(
                    game_id=game_id,
                    player_session_id=session.get('session_id', 'anonymous'),
                    game_state=game.get_game_state()
                )
            except Exception as e:
                app.logger.warning(f"Failed to save game session to database: {e}")
        
        # Check if AI played the opening move
        ai_opening_move = None
        if game.get_board():  # If there's already a tile on the board, AI played first
            ai_opening_move = {
                'played': True,
                'tile': game.get_board()[0],
                'message': f'AI played the opening tile {game.get_board()[0]} (highest double or tile)'
            }
        
        return jsonify({
            'game_id': game_id,
            'player_hand': game.get_player_hand(),
            'board': game.get_board(),
            'game_state': game.get_game_state(),
            'ai_opening_move': ai_opening_move,
            'session_score': {
                'player_wins': session['player_wins'],
                'ai_wins': session['ai_wins']
            }
        })

    @app.route('/api/play-tile', methods=['POST'])
    def play_tile():
        game_id = session.get('game_id')
        if not game_id or game_id not in app.games:
            return jsonify({'error': 'Game not found'}), 404
        
        data = request.get_json()
        tile = data.get('tile')
        position = data.get('position')  # 'left' or 'right'
        
        game = app.games[game_id]
        result = game.play_player_tile(tile, position)
        
        if result['success']:
            # Save player move to database if available
            if db_manager.engine:
                try:
                    save_game_move(
                        game_id=game_id,
                        move_number=len([m for m in game.get_game_state().get('moves', []) if m.get('player') == 'player']),
                        player_type='player',
                        tile=tile,
                        position=position,
                        board_after=game.get_board()
                    )
                except Exception as e:
                    app.logger.warning(f"Failed to save player move to database: {e}")
            
            # AI plays after player
            ai_result = game.ai_play()
            result['ai_move'] = ai_result
            
            # Save AI move to database if available and AI played
            if db_manager.engine and ai_result.get('played'):
                try:
                    save_game_move(
                        game_id=game_id,
                        move_number=len([m for m in game.get_game_state().get('moves', []) if m.get('player') == 'ai']),
                        player_type='ai',
                        tile=ai_result.get('tile'),
                        position=ai_result.get('position'),
                        board_after=game.get_board()
                    )
                except Exception as e:
                    app.logger.warning(f"Failed to save AI move to database: {e}")
            
            # Check if game ended and update session score
            game_state = game.get_game_state()
            if game_state['game_over'] and game_state['winner']:
                winner = game_state['winner']
                if winner == 'player':
                    session['player_wins'] = session.get('player_wins', 0) + 1
                else:
                    session['ai_wins'] = session.get('ai_wins', 0) + 1
                
                # Update database records if available
                if db_manager.engine:
                    try:
                        # Update game session
                        update_game_session(
                            game_id=game_id,
                            winner=winner,
                            game_state=game_state,
                            completed=True
                        )
                        
                        # Update player stats
                        game_duration = 10  # Placeholder - would calculate actual duration
                        move_count = game_state.get('player_tile_count', 7) - len(game.get_player_hand())
                        update_player_stats(
                            session_id=session.get('session_id', 'anonymous'),
                            game_won=(winner == 'player'),
                            move_count=move_count,
                            duration_minutes=game_duration
                        )
                    except Exception as e:
                        app.logger.warning(f"Failed to update game completion in database: {e}")
        
        result.update({
            'player_hand': game.get_player_hand(),
            'board': game.get_board(),
            'game_state': game.get_game_state(),
            'session_score': {
                'player_wins': session.get('player_wins', 0),
                'ai_wins': session.get('ai_wins', 0)
            }
        })
        
        return jsonify(result)

    @app.route('/api/draw-tile', methods=['POST'])
    def draw_tile():
        game_id = session.get('game_id')
        if not game_id or game_id not in app.games:
            return jsonify({'error': 'Game not found'}), 404
        
        game = app.games[game_id]
        result = game.player_draw_until_playable()
        
        # If player passed turn to AI, let AI play
        ai_result = None
        if result.get('passed'):
            ai_result = game.ai_play()
        
        result.update({
            'player_hand': game.get_player_hand(),
            'board': game.get_board(),
            'game_state': game.get_game_state(),
            'ai_move': ai_result,
            'session_score': {
                'player_wins': session.get('player_wins', 0),
                'ai_wins': session.get('ai_wins', 0)
            }
        })
        
        return jsonify(result)

    @app.route('/api/session-score', methods=['GET'])
    def get_session_score():
        return jsonify({
            'player_wins': session.get('player_wins', 0),
            'ai_wins': session.get('ai_wins', 0)
        })

    @app.route('/api/reset-score', methods=['POST'])
    def reset_session_score():
        session['player_wins'] = 0
        session['ai_wins'] = 0
        return jsonify({
            'message': 'Session score reset',
            'player_wins': 0,
            'ai_wins': 0
        })
    
    # Cost monitoring endpoints
    @app.route('/api/cost-report')
    @monitor_endpoint
    def get_cost_report():
        """Get cost optimization report"""
        try:
            project_name = app.config.get('PROJECT_NAME', 'dominoes-app')
            environment = app.config.get('ENVIRONMENT', 'dev')
            
            monitor = FreeTierMonitor()
            report = monitor.generate_cost_report(project_name, environment)
            
            return jsonify(report), 200
            
        except Exception as e:
            app.logger.error(f"Error generating cost report: {e}")
            return jsonify({
                'error': 'Failed to generate cost report',
                'message': str(e)
            }), 500
    
    @app.route('/api/free-tier-usage')
    @monitor_endpoint
    def get_free_tier_usage():
        """Get current free tier usage"""
        try:
            project_name = app.config.get('PROJECT_NAME', 'dominoes-app')
            environment = app.config.get('ENVIRONMENT', 'dev')
            
            monitor = FreeTierMonitor()
            usage = monitor.get_current_usage(project_name, environment)
            
            return jsonify(usage), 200
            
        except Exception as e:
            app.logger.error(f"Error getting free tier usage: {e}")
            return jsonify({
                'error': 'Failed to get free tier usage',
                'message': str(e)
            }), 500
    
    @app.route('/api/cost-recommendations')
    @monitor_endpoint
    def get_cost_recommendations():
        """Get cost optimization recommendations"""
        try:
            project_name = app.config.get('PROJECT_NAME', 'dominoes-app')
            environment = app.config.get('ENVIRONMENT', 'dev')
            
            monitor = FreeTierMonitor()
            usage = monitor.get_current_usage(project_name, environment)
            recommendations = monitor.get_optimization_recommendations(usage)
            
            return jsonify({
                'recommendations': recommendations,
                'total_count': len(recommendations),
                'high_priority_count': len([r for r in recommendations if r['priority'] == 'HIGH']),
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
        except Exception as e:
            app.logger.error(f"Error getting cost recommendations: {e}")
            return jsonify({
                'error': 'Failed to get cost recommendations',
                'message': str(e)
            }), 500
    
    return app