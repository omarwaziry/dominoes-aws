import random
from typing import List, Tuple, Dict, Optional

class Tile:
    def __init__(self, left: int, right: int):
        self.left = left
        self.right = right
    
    def __repr__(self):
        return f"[{self.left}|{self.right}]"
    
    def __eq__(self, other):
        if not isinstance(other, Tile):
            return False
        return (self.left == other.left and self.right == other.right) or \
               (self.left == other.right and self.right == other.left)
    
    def is_double(self):
        return self.left == self.right
    
    def has_value(self, value: int):
        return self.left == value or self.right == value
    
    def get_other_value(self, value: int):
        if self.left == value:
            return self.right
        elif self.right == value:
            return self.left
        return None
    
    def to_dict(self):
        return {'left': self.left, 'right': self.right}

class DominoesGame:
    def __init__(self):
        self.tiles = self._create_domino_set()
        self.player_hand = []
        self.ai_hand = []
        self.board = []  # List of tiles on the board
        self.boneyard = []
        self.current_player = 'player'  # 'player' or 'ai'
        self.game_over = False
        self.winner = None
        self._deal_tiles()
    
    def _create_domino_set(self) -> List[Tile]:
        """Create a standard double-six domino set (28 tiles)"""
        tiles = []
        for i in range(7):
            for j in range(i, 7):
                tiles.append(Tile(i, j))
        return tiles
    
    def _deal_tiles(self):
        """Deal 7 tiles to each player, rest go to boneyard"""
        random.shuffle(self.tiles)
        self.player_hand = self.tiles[:7]
        self.ai_hand = self.tiles[7:14]
        self.boneyard = self.tiles[14:]
        
        # Determine who starts based on highest double
        self._determine_starting_player()
    
    def _determine_starting_player(self):
        """Determine who starts based on highest double, then play AI's first move if needed"""
        # Get highest doubles from each hand
        player_doubles = [t for t in self.player_hand if t.is_double()]
        ai_doubles = [t for t in self.ai_hand if t.is_double()]
        
        player_highest_double = max(player_doubles, key=lambda t: t.left) if player_doubles else None
        ai_highest_double = max(ai_doubles, key=lambda t: t.left) if ai_doubles else None
        
        # Determine starter based on highest double
        if ai_highest_double and player_highest_double:
            if ai_highest_double.left > player_highest_double.left:
                self.current_player = 'ai'
                self._ai_play_opening_double(ai_highest_double)
            else:
                self.current_player = 'player'
        elif ai_highest_double and not player_highest_double:
            self.current_player = 'ai'
            self._ai_play_opening_double(ai_highest_double)
        elif player_highest_double and not ai_highest_double:
            self.current_player = 'player'
        else:
            # No doubles, player with highest tile starts
            player_highest = self._get_highest_tile(self.player_hand)
            ai_highest = self._get_highest_tile(self.ai_hand)
            
            if self._tile_value(ai_highest) > self._tile_value(player_highest):
                self.current_player = 'ai'
                self._ai_play_opening_tile(ai_highest)
            else:
                self.current_player = 'player'
    
    def _ai_play_opening_double(self, double_tile: Tile):
        """AI plays the opening double tile"""
        self.board.append(double_tile)
        self.ai_hand.remove(double_tile)
        self.current_player = 'player'
        
    def _ai_play_opening_tile(self, tile: Tile):
        """AI plays the opening tile (when no doubles available)"""
        self.board.append(tile)
        self.ai_hand.remove(tile)
        self.current_player = 'player'

    def _get_highest_tile(self, hand: List[Tile]) -> Tile:
        """Get the highest value tile"""
        return max(hand, key=self._tile_value)
    
    def _tile_value(self, tile: Tile) -> int:
        """Calculate tile value for comparison"""
        return tile.left + tile.right
    
    def get_board_ends(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the values at both ends of the board"""
        if not self.board:
            return None, None
        return self.board[0].left, self.board[-1].right
    
    def can_play_tile(self, tile: Tile) -> Dict[str, bool]:
        """Check if a tile can be played on either end of the board"""
        if not self.board:
            return {'left': True, 'right': True}
        
        left_end, right_end = self.get_board_ends()
        can_play_left = tile.has_value(left_end)
        can_play_right = tile.has_value(right_end)
        
        return {'left': can_play_left, 'right': can_play_right}
    
    def play_tile(self, tile: Tile, position: str, hand: List[Tile]) -> bool:
        """Play a tile on the board"""
        if tile not in hand:
            return False
        
        if not self.board:
            # First tile can be played anywhere
            self.board.append(tile)
            hand.remove(tile)
            return True
        
        left_end, right_end = self.get_board_ends()
        
        if position == 'left' and tile.has_value(left_end):
            # Orient tile correctly for left side
            if tile.right == left_end:
                self.board.insert(0, tile)
            else:  # tile.left == left_end
                self.board.insert(0, Tile(tile.right, tile.left))
            hand.remove(tile)
            return True
        
        elif position == 'right' and tile.has_value(right_end):
            # Orient tile correctly for right side
            if tile.left == right_end:
                self.board.append(tile)
            else:  # tile.right == right_end
                self.board.append(Tile(tile.right, tile.left))
            hand.remove(tile)
            return True
        
        return False
    
    def play_player_tile(self, tile_dict: Dict, position: str) -> Dict:
        """Player plays a tile"""
        if self.current_player != 'player' or self.game_over:
            return {'success': False, 'message': 'Not your turn or game over'}
        
        # Find the tile in player's hand
        tile = None
        for t in self.player_hand:
            if t.left == tile_dict['left'] and t.right == tile_dict['right']:
                tile = t
                break
        
        if not tile:
            return {'success': False, 'message': 'Tile not in your hand'}
        
        playable = self.can_play_tile(tile)
        if not playable[position]:
            return {'success': False, 'message': f'Cannot play tile on {position} side'}
        
        if self.play_tile(tile, position, self.player_hand):
            self.current_player = 'ai'
            self._check_game_over()
            return {'success': True, 'message': 'Tile played successfully'}
        
        return {'success': False, 'message': 'Failed to play tile'}
    
    def ai_play(self) -> Dict:
        """AI makes a move - draws tiles until it can play, then plays"""
        if self.current_player != 'ai' or self.game_over:
            return {'played': False, 'message': 'Not AI turn or game over'}
        
        drawn_tiles = []
        
        # Keep drawing until AI can play or boneyard is empty
        while True:
            # Find playable tiles
            playable_moves = []
            for tile in self.ai_hand:
                playable = self.can_play_tile(tile)
                if playable['left']:
                    playable_moves.append((tile, 'left'))
                if playable['right']:
                    playable_moves.append((tile, 'right'))
            
            if playable_moves:
                # AI can play - choose the highest value tile
                best_move = max(playable_moves, key=lambda x: self._tile_value(x[0]))
                tile, position = best_move
                
                if self.play_tile(tile, position, self.ai_hand):
                    self.current_player = 'player'
                    self._check_game_over()
                    
                    message = f'AI played {tile} on {position} side'
                    if drawn_tiles:
                        message = f'AI drew {len(drawn_tiles)} tile(s), then played {tile} on {position} side'
                    
                    return {
                        'played': True, 
                        'tile': tile.to_dict(), 
                        'position': position,
                        'drew_count': len(drawn_tiles),
                        'message': message
                    }
            
            # AI cannot play, try to draw
            if self.boneyard:
                drawn_tile = self.boneyard.pop()
                self.ai_hand.append(drawn_tile)
                drawn_tiles.append(drawn_tile)
            else:
                # No more tiles to draw, AI must pass
                self.current_player = 'player'
                message = 'AI passed (no playable tiles)'
                if drawn_tiles:
                    message = f'AI drew {len(drawn_tiles)} tile(s) but still cannot play - passed'
                
                return {
                    'played': False, 
                    'drew_tile': len(drawn_tiles) > 0,
                    'drew_count': len(drawn_tiles),
                    'message': message
                }
    
    def player_draw_until_playable(self) -> Dict:
        """Player draws tiles until they can play or boneyard is empty"""
        if self.current_player != 'player' or self.game_over:
            return {'success': False, 'message': 'Not your turn or game over'}
        
        if not self.boneyard:
            return {'success': False, 'message': 'No tiles left to draw'}
        
        drawn_tiles = []
        
        # Keep drawing until player can play or boneyard is empty
        while True:
            # Check if player can play with current hand
            can_play_any = False
            for tile in self.player_hand:
                playable = self.can_play_tile(tile)
                if playable['left'] or playable['right']:
                    can_play_any = True
                    break
            
            if can_play_any:
                # Player can play with current hand
                message = 'You can now play a tile'
                if drawn_tiles:
                    message = f'Drew {len(drawn_tiles)} tile(s) - you can now play'
                
                return {
                    'success': True,
                    'drew_count': len(drawn_tiles),
                    'can_play': True,
                    'message': message
                }
            
            # Player cannot play, try to draw
            if self.boneyard:
                drawn_tile = self.boneyard.pop()
                self.player_hand.append(drawn_tile)
                drawn_tiles.append(drawn_tile)
            else:
                # No more tiles to draw, player must pass
                self.current_player = 'ai'
                message = 'No playable tiles - turn passed to AI'
                if drawn_tiles:
                    message = f'Drew {len(drawn_tiles)} tile(s) but still cannot play - turn passed to AI'
                
                return {
                    'success': True,
                    'drew_count': len(drawn_tiles),
                    'can_play': False,
                    'passed': True,
                    'message': message
                }
    
    def player_draw_tile(self) -> Dict:
        """Legacy method - now calls the new draw until playable method"""
        return self.player_draw_until_playable()
    
    def _check_game_over(self):
        """Check if the game is over"""
        if not self.player_hand:
            self.game_over = True
            self.winner = 'player'
        elif not self.ai_hand:
            self.game_over = True
            self.winner = 'ai'
        elif not self.boneyard:
            # Check if anyone can play
            player_can_play = any(self.can_play_tile(t)['left'] or self.can_play_tile(t)['right'] 
                                for t in self.player_hand)
            ai_can_play = any(self.can_play_tile(t)['left'] or self.can_play_tile(t)['right'] 
                            for t in self.ai_hand)
            
            if not player_can_play and not ai_can_play:
                self.game_over = True
                # Winner is player with lowest total pip count
                player_total = sum(self._tile_value(t) for t in self.player_hand)
                ai_total = sum(self._tile_value(t) for t in self.ai_hand)
                self.winner = 'player' if player_total < ai_total else 'ai'
    
    def get_player_hand(self) -> List[Dict]:
        """Get player's hand as list of dictionaries"""
        return [tile.to_dict() for tile in self.player_hand]
    
    def get_board(self) -> List[Dict]:
        """Get board state as list of dictionaries"""
        return [tile.to_dict() for tile in self.board]
    
    def can_player_play_any_tile(self) -> bool:
        """Check if current player can play any tile from their hand"""
        hand = self.player_hand if self.current_player == 'player' else self.ai_hand
        
        for tile in hand:
            playable = self.can_play_tile(tile)
            if playable['left'] or playable['right']:
                return True
        return False

    def get_game_state(self) -> Dict:
        """Get current game state"""
        left_end, right_end = self.get_board_ends()
        return {
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner,
            'player_tile_count': len(self.player_hand),
            'ai_tile_count': len(self.ai_hand),
            'boneyard_count': len(self.boneyard),
            'board_ends': {'left': left_end, 'right': right_end},
            'player_can_play': self.can_player_play_any_tile() if self.current_player == 'player' else True
        }
    
    def get_starting_info(self) -> Dict:
        """Get information about who starts and why"""
        player_doubles = [t for t in self.player_hand if t.is_double()]
        ai_doubles = [t for t in self.ai_hand if t.is_double()]
        
        player_highest_double = max(player_doubles, key=lambda t: t.left) if player_doubles else None
        ai_highest_double = max(ai_doubles, key=lambda t: t.left) if ai_doubles else None
        
        if ai_highest_double and player_highest_double:
            if ai_highest_double.left > player_highest_double.left:
                return {
                    'starter': 'ai',
                    'reason': f'AI has highest double: {ai_highest_double}',
                    'opening_tile': ai_highest_double.to_dict()
                }
            else:
                return {
                    'starter': 'player',
                    'reason': f'Player has highest double: {player_highest_double}',
                    'opening_tile': None
                }
        elif ai_highest_double:
            return {
                'starter': 'ai',
                'reason': f'AI has only double: {ai_highest_double}',
                'opening_tile': ai_highest_double.to_dict()
            }
        elif player_highest_double:
            return {
                'starter': 'player',
                'reason': f'Player has only double: {player_highest_double}',
                'opening_tile': None
            }
        else:
            player_highest = self._get_highest_tile(self.player_hand)
            ai_highest = self._get_highest_tile(self.ai_hand)
            
            if self._tile_value(ai_highest) > self._tile_value(player_highest):
                return {
                    'starter': 'ai',
                    'reason': f'AI has highest tile: {ai_highest}',
                    'opening_tile': ai_highest.to_dict()
                }
            else:
                return {
                    'starter': 'player',
                    'reason': f'Player has highest tile: {player_highest}',
                    'opening_tile': None
                }