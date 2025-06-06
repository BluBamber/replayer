#!/usr/bin/env python3
"""
ROBLOX Game Replay System - Flask Application
Deploy this to Render.com as a Web Service
"""

import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
import threading
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# Database setup
DATABASE = 'roblox_replays.db'

def init_db():
    """Initialize the SQLite database"""
    print("Initializing database...")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            server_id TEXT PRIMARY KEY,
            place_id INTEGER,
            creator_id INTEGER,
            game_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_frame INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT,
            frame_number INTEGER,
            timestamp REAL,
            parts_data TEXT,
            players_data TEXT,
            game_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (server_id) REFERENCES servers (server_id)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_server_frame ON frames (server_id, frame_number)
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db_exists():
    """Ensure database exists and is initialized"""
    if not os.path.exists(DATABASE):
        print("Database file doesn't exist, creating...")
        init_db()
    else:
        # Check if tables exist
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='frames'")
            if not cursor.fetchone():
                print("Tables don't exist, initializing...")
                conn.close()
                init_db()
            else:
                conn.close()
                print("Database already exists and is properly initialized")
        except Exception as e:
            print(f"Error checking database: {e}")
            print("Reinitializing database...")
            init_db()

# Initialize database on startup
ensure_db_exists()

# API Routes
@app.route('/api/record', methods=['POST'])
def record_frame():
    """Receive frame data from ROBLOX server"""
    try:
        # Ensure database exists before processing
        ensure_db_exists()
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            # Try to parse as JSON from text
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = request.form.to_dict()
        
        if not data:
            print("ERROR: No data provided")
            return jsonify({'error': 'No data provided'}), 400
        
        print(f"Received data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        server_id = data.get('ServerId')
        if not server_id:
            print(f"ERROR: ServerId missing. Data: {data}")
            return jsonify({'error': 'ServerId required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Handle server start
        if data.get('Type') == 'ServerStart':
            print(f"Registering server: {server_id}")
            cursor.execute('''
                INSERT OR REPLACE INTO servers (server_id, place_id, creator_id, game_name)
                VALUES (?, ?, ?, ?)
            ''', (server_id, data.get('PlaceId'), data.get('CreatorId'), data.get('GameName')))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Server registered'})
        
        # Handle frame data
        frame_number = data.get('Frame', 0)
        timestamp = data.get('Timestamp', time.time())
        parts_data = json.dumps(data.get('Parts', []))
        players_data = json.dumps(data.get('Players', []))
        game_info = json.dumps(data.get('GameInfo', {}))
        
        print(f"Processing frame {frame_number} for server {server_id}")
        print(f"Parts count: {len(data.get('Parts', []))}, Players count: {len(data.get('Players', []))}")
        
        # Ensure server exists first
        cursor.execute('''
            INSERT OR IGNORE INTO servers (server_id, place_id, creator_id, game_name)
            VALUES (?, ?, ?, ?)
        ''', (server_id, data.get('GameInfo', {}).get('PlaceId'), 0, 'Unknown Game'))
        
        # Insert frame
        cursor.execute('''
            INSERT INTO frames (server_id, frame_number, timestamp, parts_data, players_data, game_info)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (server_id, frame_number, timestamp, parts_data, players_data, game_info))
        
        # Update server last frame
        cursor.execute('''
            UPDATE servers SET last_frame = ? WHERE server_id = ?
        ''', (frame_number, server_id))
        
        conn.commit()
        conn.close()
        
        print(f"Successfully stored frame {frame_number}")
        return jsonify({'status': 'success', 'frame': frame_number})
        
    except Exception as e:
        print(f"ERROR in record_frame: {str(e)}")
        print(f"Request data: {request.data}")
        print(f"Request headers: {dict(request.headers)}")
        
        # Try to reinitialize database if there's a database error
        if "no such table" in str(e).lower():
            print("Database table missing, reinitializing...")
            try:
                init_db()
                return jsonify({'error': 'Database reinitialized, please retry'}), 503
            except Exception as init_error:
                print(f"Failed to reinitialize database: {init_error}")
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers', methods=['GET'])
def get_servers():
    """Get list of available servers"""
    try:
        ensure_db_exists()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.*, COUNT(f.id) as frame_count
            FROM servers s
            LEFT JOIN frames f ON s.server_id = f.server_id
            GROUP BY s.server_id
            ORDER BY s.created_at DESC
        ''')
        
        servers = []
        for row in cursor.fetchall():
            servers.append({
                'server_id': row['server_id'],
                'place_id': row['place_id'],
                'creator_id': row['creator_id'],
                'game_name': row['game_name'],
                'created_at': row['created_at'],
                'last_frame': row['last_frame'],
                'frame_count': row['frame_count']
            })
        
        conn.close()
        return jsonify(servers)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/frames', methods=['GET'])
def get_server_frames(server_id):
    """Get all frames for a specific server"""
    try:
        ensure_db_exists()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT frame_number, timestamp, parts_data, players_data, game_info
            FROM frames
            WHERE server_id = ?
            ORDER BY frame_number ASC
        ''', (server_id,))
        
        frames = []
        for row in cursor.fetchall():
            frames.append({
                'frame': row['frame_number'],
                'timestamp': row['timestamp'],
                'parts': json.loads(row['parts_data']),
                'players': json.loads(row['players_data']),
                'gameInfo': json.loads(row['game_info'])
            })
        
        conn.close()
        return jsonify(frames)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/frame/<int:frame_number>', methods=['GET'])
def get_specific_frame(server_id, frame_number):
    """Get a specific frame"""
    try:
        ensure_db_exists()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT frame_number, timestamp, parts_data, players_data, game_info
            FROM frames
            WHERE server_id = ? AND frame_number = ?
        ''', (server_id, frame_number))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Frame not found'}), 404
        
        frame_data = {
            'frame': row['frame_number'],
            'timestamp': row['timestamp'],
            'parts': json.loads(row['parts_data']),
            'players': json.loads(row['players_data']),
            'gameInfo': json.loads(row['game_info'])
        }
        
        conn.close()
        return jsonify(frame_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        ensure_db_exists()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM servers")
        server_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM frames")
        frame_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'servers': server_count,
            'frames': frame_count
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Web Interface
@app.route('/')
def index():
    """Serve the main replay viewer interface"""
    return render_template_string(HTML_TEMPLATE)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROBLOX Game Replay Viewer</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            overflow: hidden;
        }
        
        #container {
            width: 100vw;
            height: 100vh;
            position: relative;
        }
        
        #renderer {
            display: block;
        }
        
        #controls {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        #controls button {
            background: linear-gradient(45deg, #00c6ff, #0072ff);
            border: none;
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        
        #controls button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 114, 255, 0.4);
        }
        
        #controls button:disabled {
            background: #666;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        #frameSlider {
            width: 300px;
            height: 5px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
            outline: none;
            -webkit-appearance: none;
        }
        
        #frameSlider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #00c6ff;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0, 198, 255, 0.5);
        }
        
        #info {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px;
            border-radius: 10px;
            font-size: 14px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        #serverSelector {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        #serverSelector select {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 8px;
            border-radius: 5px;
            margin-left: 10px;
        }
        
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 18px;
            text-align: center;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="loading" class="loading">Loading ROBLOX Replay System...</div>
        
        <div id="info" style="display: none;">
            <div><strong>Server:</strong> <span id="currentServer">None</span></div>
            <div><strong>Frame:</strong> <span id="currentFrame">0</span> / <span id="totalFrames">0</span></div>
            <div><strong>Players:</strong> <span id="playerCount">0</span></div>
            <div><strong>Parts:</strong> <span id="partCount">0</span></div>
            <div><strong>Game:</strong> <span id="gameName">Unknown</span></div>
        </div>
        
        <div id="serverSelector" style="display: none;">
            <label for="serverSelect">Select Server:</label>
            <select id="serverSelect">
                <option value="">Choose a server...</option>
            </select>
            <button id="loadServer">Load</button>
        </div>
        
        <div id="controls" style="display: none;">
            <button id="playPause">Play</button>
            <button id="prevFrame">◀</button>
            <input type="range" id="frameSlider" min="0" max="100" value="0">
            <button id="nextFrame">▶</button>
            <button id="resetCamera">Reset Camera</button>
            <span style="color: white; font-size: 12px;">Speed:</span>
            <select id="speedControl" style="background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.3); padding: 5px; border-radius: 3px;">
                <option value="0.5">0.5x</option>
                <option value="1" selected>1x</option>
                <option value="2">2x</option>
                <option value="4">4x</option>
            </select>
        </div>
    </div>

    <script>
        // Three.js scene setup
        let scene, camera, renderer;
        let gameData = [];
        let currentFrame = 0;
        let isPlaying = false;
        let playbackSpeed = 1;
        let parts = new Map();
        let players = new Map();
        let currentServerId = null;
        
        // Camera controls
        let cameraControls = {
            mouseX: 0,
            mouseY: 0,
            mouseDown: false,
            distance: 100,
            phi: Math.PI / 4,
            theta: 0
        };
        
        // Initialize Three.js scene
        function initScene() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87CEEB);
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            
            document.getElementById('container').appendChild(renderer.domElement);
            renderer.domElement.id = 'renderer';
            
            // Add lights
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(50, 50, 50);
            directionalLight.castShadow = true;
            scene.add(directionalLight);
            
            // Add grid
            const gridHelper = new THREE.GridHelper(200, 50, 0x888888, 0x444444);
            scene.add(gridHelper);
            
            setupCameraControls();
            updateCamera();
            animate();
        }
        
        function setupCameraControls() {
            const canvas = renderer.domElement;
            
            canvas.addEventListener('mousedown', (e) => {
                cameraControls.mouseDown = true;
                cameraControls.mouseX = e.clientX;
                cameraControls.mouseY = e.clientY;
            });
            
            canvas.addEventListener('mouseup', () => {
                cameraControls.mouseDown = false;
            });
            
            canvas.addEventListener('mousemove', (e) => {
                if (!cameraControls.mouseDown) return;
                
                const deltaX = e.clientX - cameraControls.mouseX;
                const deltaY = e.clientY - cameraControls.mouseY;
                
                cameraControls.theta -= deltaX * 0.01;
                cameraControls.phi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraControls.phi - deltaY * 0.01));
                
                cameraControls.mouseX = e.clientX;
                cameraControls.mouseY = e.clientY;
                
                updateCamera();
            });
            
            canvas.addEventListener('wheel', (e) => {
                cameraControls.distance = Math.max(10, Math.min(500, cameraControls.distance + e.deltaY * 0.1));
                updateCamera();
            });
        }
        
        function updateCamera() {
            const x = cameraControls.distance * Math.sin(cameraControls.phi) * Math.cos(cameraControls.theta);
            const y = cameraControls.distance * Math.cos(cameraControls.phi);
            const z = cameraControls.distance * Math.sin(cameraControls.phi) * Math.sin(cameraControls.theta);
            
            camera.position.set(x, y, z);
            camera.lookAt(0, 0, 0);
        }
        
        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        
        // Material mapping for ROBLOX materials
        function getMaterial(materialName, color) {
            const materials = {
                'Plastic': new THREE.MeshLambertMaterial({ color: new THREE.Color(color.R, color.G, color.B) }),
                'Wood': new THREE.MeshLambertMaterial({ 
                    color: new THREE.Color(color.R * 0.8, color.G * 0.6, color.B * 0.4) 
                }),
                'Metal': new THREE.MeshPhongMaterial({ 
                    color: new THREE.Color(color.R, color.G, color.B),
                    shininess: 100 
                }),
                'Neon': new THREE.MeshBasicMaterial({ 
                    color: new THREE.Color(color.R, color.G, color.B),
                    transparent: true,
                    opacity: 0.8
                })
            };
            
            return materials[materialName] || materials['Plastic'];
        }
        
        function createPart(partData) {
            const geometry = new THREE.BoxGeometry(partData.Size.X, partData.Size.Y, partData.Size.Z);
            const material = getMaterial(partData.Material, partData.Color);
            
            if (partData.Transparency > 0) {
                material.transparent = true;
                material.opacity = 1 - partData.Transparency;
            }
            
            const mesh = new THREE.Mesh(geometry, material);
            mesh.position.set(partData.Position.X, partData.Position.Y, partData.Position.Z);
            mesh.rotation.set(
                partData.Rotation.X * Math.PI / 180,
                partData.Rotation.Y * Math.PI / 180,
                partData.Rotation.Z * Math.PI / 180
            );
            
            mesh.userData = { name: partData.Name, path: partData.FullPath };
            
            return mesh;
        }
        
        function createPlayer(playerData) {
            // Simple player representation
            const geometry = new THREE.CapsuleGeometry(1, 4, 4, 8);
            const material = new THREE.MeshLambertMaterial({ color: 0x00ff00 });
            const mesh = new THREE.Mesh(geometry, material);
            
            mesh.position.set(playerData.Position.X, playerData.Position.Y + 2, playerData.Position.Z);
            mesh.userData = { name: playerData.Name, userId: playerData.UserId };
            
            return mesh;
        }
        
        function renderFrame(frameData) {
            if (!frameData) return;
            
            // Clear existing objects
            parts.forEach(part => scene.remove(part));
            players.forEach(player => scene.remove(player));
            parts.clear();
            players.clear();
            
            // Add parts
            if (frameData.parts) {
                frameData.parts.forEach(partData => {
                    const part = createPart(partData);
                    scene.add(part);
                    parts.set(partData.FullPath, part);
                });
            }
            
            // Add players
            if (frameData.players) {
                frameData.players.forEach(playerData => {
                    const player = createPlayer(playerData);
                    scene.add(player);
                    players.set(playerData.Name, player);
                });
            }
            
            // Update UI
            document.getElementById('currentFrame').textContent = frameData.frame;
            document.getElementById('playerCount').textContent = frameData.players ? frameData.players.length : 0;
            document.getElementById('partCount').textContent = frameData.parts ? frameData.parts.length : 0;
        }
        
        // API functions
        async function loadServers() {
            try {
                const response = await fetch('/api/servers');
                const servers = await response.json();
                
                const select = document.getElementById('serverSelect');
                select.innerHTML = '<option value="">Choose a server...</option>';
                
                servers.forEach(server => {
                    const option = document.createElement('option');
                    option.value = server.server_id;
                    option.textContent = `${server.game_name || 'Unknown Game'} (${server.frame_count} frames)`;
                    select.appendChild(option);
                });
                
                return servers;
            } catch (error) {
                console.error('Failed to load servers:', error);
                return [];
            }
        }
        
        async function loadServerData(serverId) {
            try {
                const response = await fetch(`/api/server/${serverId}/frames`);
                const frames = await response.json();
                
                gameData = frames;
                currentFrame = 0;
                currentServerId = serverId;
                
                if (frames.length > 0) {
                    document.getElementById('totalFrames').textContent = frames.length;
                    document.getElementById('frameSlider').max = frames.length - 1;
                    document.getElementById('currentServer').textContent = serverId;
                    
                    if (frames[0].gameInfo && frames[0].gameInfo.PlaceId) {
                        document.getElementById('gameName').textContent = `Place ${frames[0].gameInfo.PlaceId}`;
                    }
                    
                    renderFrame(frames[0]);
                    return true;
                }
                
                return false;
            } catch (error) {
                console.error('Failed to load server data:', error);
                return false;
            }
        }
        
        // Control functions
        function playPause() {
            isPlaying = !isPlaying;
            document.getElementById('playPause').textContent = isPlaying ? 'Pause' : 'Play';
            
            if (isPlaying) {
                playLoop();
            }
        }
        
        function playLoop() {
            if (!isPlaying) {
                return;
            }
            
            if (currentFrame >= gameData.length - 1) {
                isPlaying = false;
                document.getElementById('playPause').textContent = 'Play';
                return;
            }
            
            currentFrame++;
            renderFrame(gameData[currentFrame]);
            document.getElementById('frameSlider').value = currentFrame;
            
            setTimeout(playLoop, 1000 / playbackSpeed);
        }
        
        function nextFrame() {
            if (currentFrame < gameData.length - 1) {
                currentFrame++;
                renderFrame(gameData[currentFrame]);
                document.getElementById('frameSlider').value = currentFrame;
            }
        }
        
        function prevFrame() {
            if (currentFrame > 0) {
                currentFrame--;
                renderFrame(gameData[currentFrame]);
                document.getElementById('frameSlider').value = currentFrame;
            }
        }
        
        function resetCamera() {
            cameraControls.distance = 100;
            cameraControls.phi = Math.PI / 4;
            cameraControls.theta = 0;
            updateCamera();
        }
        
        // Event listeners
        document.addEventListener('DOMContentLoaded', async () => {
            initScene();
            
            // Load available servers
            await loadServers();
            
            // Show UI
            document.getElementById('loading').style.display = 'none';
            document.getElementById('serverSelector').style.display = 'block';
            
            // Setup controls
            document.getElementById('loadServer').addEventListener('click', async () => {
                const serverId = document.getElementById('serverSelect').value;
                if (serverId) {
                    document.getElementById('loading').style.display = 'block';
                    const success = await loadServerData(serverId);
                    document.getElementById('loading').style.display = 'none';
                    
                    if (success) {
                        document.getElementById('info').style.display = 'block';
                        document.getElementById('controls').style.display = 'flex';
                    }
                }
            });
            
            document.getElementById('playPause').addEventListener('click', playPause);
            document.getElementById('nextFrame').addEventListener('click', nextFrame);
            document.getElementById('prevFrame').addEventListener('click', prevFrame);
            document.getElementById('resetCamera').addEventListener('click', resetCamera);
            
            document.getElementById('frameSlider').addEventListener('input', (e) => {
                currentFrame = parseInt(e.target.value);
                if (gameData[currentFrame]) {
                    renderFrame(gameData[currentFrame]);
                }
            });
            
            document.getElementById('speedControl').addEventListener('change', (e) => {
                playbackSpeed = parseFloat(e.target.value);
            });
        });
        
        // Handle window resize
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    # Initialize database on startup
    print("Starting ROBLOX Replay System...")
    init_db()
    
    # Get port from environment (Render uses PORT env var)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
