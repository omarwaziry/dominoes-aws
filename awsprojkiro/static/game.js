class DominoesGameUI {
    constructor() {
        this.gameId = null;
        this.selectedTile = null;
        this.gameState = null;
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        document.getElementById('new-game-btn').addEventListener('click', () => this.startNewGame());
        document.getElementById('play-again-btn').addEventListener('click', () => this.startNewGame());
        document.getElementById('boneyard-pile').addEventListener('click', () => this.drawTile());
        document.getElementById('reset-score-btn').addEventListener('click', () => this.resetSessionScore());
        
        // Load session score on page load
        this.loadSessionScore();
    }

    async startNewGame() {
        try {
            const response = await fetch('/api/new-game', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (response.ok) {
                this.gameId = data.game_id;
                this.selectedTile = null;
                this.updateGameDisplay(data);
                this.updateSessionScore(data.session_score);
                this.addMessage('New game started!', 'success');
                
                // Handle AI opening move
                if (data.ai_opening_move && data.ai_opening_move.played) {
                    this.addMessage(data.ai_opening_move.message, 'info');
                }
                
                document.getElementById('game-over').classList.add('hidden');
            } else {
                this.addMessage('Failed to start new game', 'error');
            }
        } catch (error) {
            this.addMessage('Error starting new game: ' + error.message, 'error');
        }
    }

    async playTile(tile, position) {
        if (!this.gameId) return;

        try {
            const response = await fetch('/api/play-tile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tile: tile,
                    position: position
                })
            });

            const data = await response.json();
            if (data.success) {
                this.selectedTile = null;
                this.clearPlayableAreas();
                this.updateGameDisplay(data);
                this.updateSessionScore(data.session_score);
                this.addMessage(data.message, 'success');
                
                if (data.ai_move) {
                    if (data.ai_move.played) {
                        this.addMessage(data.ai_move.message, 'info');
                    } else {
                        this.addMessage(data.ai_move.message, 'info');
                    }
                }
            } else {
                this.addMessage(data.message, 'error');
            }
        } catch (error) {
            this.addMessage('Error playing tile: ' + error.message, 'error');
        }
    }

    async drawTile() {
        if (!this.gameId) return;

        try {
            const response = await fetch('/api/draw-tile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            if (data.success) {
                this.updateGameDisplay(data);
                this.updateSessionScore(data.session_score);
                this.addMessage(data.message, 'info');
                
                // Handle AI move if player passed
                if (data.ai_move) {
                    if (data.ai_move.played) {
                        this.addMessage(data.ai_move.message, 'info');
                    } else {
                        this.addMessage(data.ai_move.message, 'info');
                    }
                }
            } else {
                this.addMessage(data.message, 'error');
            }
        } catch (error) {
            this.addMessage('Error drawing tile: ' + error.message, 'error');
        }
    }

    updateGameDisplay(data) {
        this.gameState = data.game_state;
        
        // Update game info
        document.getElementById('player-count').textContent = data.game_state.player_tile_count;
        document.getElementById('ai-count').textContent = data.game_state.ai_tile_count;
        document.getElementById('boneyard-count').textContent = data.game_state.boneyard_count;
        document.getElementById('current-turn').textContent = 
            data.game_state.current_player === 'player' ? 'Your Turn' : 'AI Turn';

        // Update board
        this.renderBoard(data.board);
        
        // Update player hand
        this.renderPlayerHand(data.player_hand);
        
        // Update boneyard display
        document.getElementById('boneyard-display-count').textContent = data.game_state.boneyard_count;
        const boneyardPile = document.getElementById('boneyard-pile');
        const canDraw = data.game_state.current_player === 'player' && 
                       data.game_state.boneyard_count > 0 && 
                       !data.game_state.game_over;
        
        if (canDraw) {
            boneyardPile.classList.remove('disabled');
        } else {
            boneyardPile.classList.add('disabled');
        }

        // Check if player needs to draw tiles
        this.checkIfPlayerNeedsToDrawTiles();

        // Check for game over
        if (data.game_state.game_over) {
            this.showGameOver(data.game_state.winner);
        }
    }

    renderBoard(board) {
        const boardContainer = document.getElementById('board-tiles');
        boardContainer.innerHTML = '';

        if (board.length === 0) {
            boardContainer.innerHTML = '<div class="board-empty-message">Click a tile to select it, then click here to play!</div>';
            // Add clickable area for empty board
            this.createBoardClickArea(boardContainer, true);
            return;
        }

        // Add left click area
        const leftClickArea = this.createBoardClickArea(boardContainer, false, 'left');
        boardContainer.appendChild(leftClickArea);

        // Add board tiles
        board.forEach(tile => {
            const tileElement = this.createTileElement(tile, false);
            boardContainer.appendChild(tileElement);
        });

        // Add right click area
        const rightClickArea = this.createBoardClickArea(boardContainer, false, 'right');
        boardContainer.appendChild(rightClickArea);
    }

    renderPlayerHand(hand) {
        const handContainer = document.getElementById('hand-tiles');
        handContainer.innerHTML = '';

        if (hand.length === 0) {
            handContainer.innerHTML = '<div style="color: #999; font-style: italic;">No tiles in hand</div>';
            return;
        }

        hand.forEach(tile => {
            const tileElement = this.createTileElement(tile, true);
            this.makeTileClickable(tileElement, tile);
            handContainer.appendChild(tileElement);
        });
    }

    createTileElement(tile, isClickable) {
        const tileDiv = document.createElement('div');
        tileDiv.className = 'tile';
        tileDiv.dataset.left = tile.left;
        tileDiv.dataset.right = tile.right;

        const leftHalf = document.createElement('div');
        leftHalf.className = `tile-half dots-${tile.left}`;
        
        const rightHalf = document.createElement('div');
        rightHalf.className = `tile-half dots-${tile.right}`;

        tileDiv.appendChild(leftHalf);
        tileDiv.appendChild(rightHalf);

        return tileDiv;
    }

    createBoardClickArea(container, isEmpty = false, position = 'center') {
        const clickArea = document.createElement('div');
        clickArea.className = `play-area play-area-${position}`;
        clickArea.dataset.position = position;
        
        if (isEmpty) {
            clickArea.style.position = 'absolute';
            clickArea.style.top = '50%';
            clickArea.style.left = '50%';
            clickArea.style.transform = 'translate(-50%, -50%)';
            clickArea.style.width = '200px';
            clickArea.style.height = '80px';
            container.appendChild(clickArea);
        }
        
        this.setupBoardClickArea(clickArea);
        return clickArea;
    }

    makeTileClickable(tileElement, tile) {
        tileElement.style.cursor = 'pointer';
        tileElement.dataset.tileData = JSON.stringify(tile);

        tileElement.addEventListener('click', (e) => {
            if (this.gameState && this.gameState.current_player !== 'player') {
                this.addMessage("It's not your turn!", 'error');
                return;
            }

            if (this.gameState && this.gameState.game_over) {
                this.addMessage("Game is over!", 'error');
                return;
            }

            this.selectTile(tileElement, tile);
        });
    }

    selectTile(tileElement, tile) {
        // Clear previous selection
        document.querySelectorAll('.tile.selected').forEach(t => {
            t.classList.remove('selected');
        });
        this.clearPlayableAreas();

        // Select new tile
        tileElement.classList.add('selected');
        this.selectedTile = tile;
        
        // Show where this tile can be played
        this.showPlayableAreas(tile);
        
        this.addMessage(`Selected tile [${tile.left}|${tile.right}] - Click on the board to play it`, 'info');
    }

    setupBoardClickArea(clickArea) {
        clickArea.addEventListener('click', (e) => {
            if (!this.selectedTile) {
                this.addMessage('Select a tile from your hand first!', 'error');
                return;
            }

            if (this.gameState && this.gameState.current_player !== 'player') {
                this.addMessage("It's not your turn!", 'error');
                return;
            }

            if (!clickArea.classList.contains('playable')) {
                this.addMessage('Cannot play the selected tile here!', 'error');
                return;
            }

            const position = clickArea.dataset.position === 'center' ? 'left' : clickArea.dataset.position;
            this.playTile(this.selectedTile, position);
        });
    }

    showPlayableAreas(tile) {
        const playAreas = document.querySelectorAll('.play-area');
        const canPlay = this.canPlayTile(tile);
        
        playAreas.forEach(area => {
            const position = area.dataset.position;
            let isPlayable = false;
            
            if (position === 'center' && (!this.gameState || !this.gameState.board_ends || 
                (this.gameState.board_ends.left === null && this.gameState.board_ends.right === null))) {
                isPlayable = true;
            } else if (position === 'left' && canPlay.left) {
                isPlayable = true;
            } else if (position === 'right' && canPlay.right) {
                isPlayable = true;
            }
            
            if (isPlayable) {
                area.classList.add('playable');
            } else {
                area.classList.remove('playable');
            }
        });
    }

    clearPlayableAreas() {
        document.querySelectorAll('.play-area').forEach(area => {
            area.classList.remove('playable');
        });
    }

    canPlayTile(tile) {
        if (!this.gameState || !this.gameState.board_ends) {
            return { left: true, right: true };
        }

        const { left: leftEnd, right: rightEnd } = this.gameState.board_ends;
        
        if (leftEnd === null && rightEnd === null) {
            return { left: true, right: true };
        }

        const canPlayLeft = leftEnd !== null && (tile.left === leftEnd || tile.right === leftEnd);
        const canPlayRight = rightEnd !== null && (tile.left === rightEnd || tile.right === rightEnd);

        return { left: canPlayLeft, right: canPlayRight };
    }

    checkIfPlayerNeedsToDrawTiles() {
        if (!this.gameState || this.gameState.current_player !== 'player' || this.gameState.game_over) {
            return;
        }

        // Check if player can play any tile
        if (this.gameState.player_can_play === false && this.gameState.boneyard_count > 0) {
            this.addMessage('You cannot play any tiles. Click the boneyard to draw until you can play!', 'info');
        }
    }

    showGameOver(winner) {
        const gameOverDiv = document.getElementById('game-over');
        const resultText = document.getElementById('game-result');
        
        if (winner === 'player') {
            resultText.textContent = '🎉 You Won! 🎉';
            resultText.style.color = '#4CAF50';
            this.addMessage('Congratulations! You won this game!', 'success');
        } else {
            resultText.textContent = '😔 AI Won! 😔';
            resultText.style.color = '#f44336';
            this.addMessage('AI won this game. Better luck next time!', 'info');
        }
        
        // Update final score display in modal
        const playerWins = document.getElementById('player-wins').textContent;
        const aiWins = document.getElementById('ai-wins').textContent;
        document.getElementById('final-player-score').textContent = playerWins;
        document.getElementById('final-ai-score').textContent = aiWins;
        
        gameOverDiv.classList.remove('hidden');
        
        // Show updated session score in message
        this.addMessage(`Session Score - You: ${playerWins}, AI: ${aiWins}`, 'info');
    }

    async loadSessionScore() {
        try {
            const response = await fetch('/api/session-score');
            const data = await response.json();
            if (response.ok) {
                this.updateSessionScore(data);
            }
        } catch (error) {
            console.error('Error loading session score:', error);
        }
    }

    async resetSessionScore() {
        try {
            const response = await fetch('/api/reset-score', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (response.ok) {
                this.updateSessionScore(data);
                this.addMessage('Session score reset!', 'info');
            } else {
                this.addMessage('Failed to reset score', 'error');
            }
        } catch (error) {
            this.addMessage('Error resetting score: ' + error.message, 'error');
        }
    }

    updateSessionScore(scoreData) {
        if (scoreData) {
            document.getElementById('player-wins').textContent = scoreData.player_wins;
            document.getElementById('ai-wins').textContent = scoreData.ai_wins;
        }
    }

    addMessage(message, type = 'info') {
        const messageLog = document.getElementById('message-log');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
        
        messageLog.appendChild(messageDiv);
        messageLog.scrollTop = messageLog.scrollHeight;
    }
}

// Initialize the game when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.game = new DominoesGameUI();
});