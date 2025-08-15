from flask import Flask, render_template, request, jsonify, session
import uuid
from dominoes_game import DominoesGame

app = Flask(__name__)
app.secret_key = 'dominoes-secret-key-change-in-production'

# Store active games in memory (use Redis/database for production)
games = {}

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
    games[game_id] = game
    session['game_id'] = game_id
    
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
    if not game_id or game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    data = request.get_json()
    tile = data.get('tile')
    position = data.get('position')  # 'left' or 'right'
    
    game = games[game_id]
    result = game.play_player_tile(tile, position)
    
    if result['success']:
        # AI plays after player
        ai_result = game.ai_play()
        result['ai_move'] = ai_result
        
        # Check if game ended and update session score
        game_state = game.get_game_state()
        if game_state['game_over'] and game_state['winner']:
            if game_state['winner'] == 'player':
                session['player_wins'] = session.get('player_wins', 0) + 1
            else:
                session['ai_wins'] = session.get('ai_wins', 0) + 1
    
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
    if not game_id or game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
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

if __name__ == '__main__':
    app.run(debug=True)