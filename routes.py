#!/usr/bin/env python3
"""
ROBLOX Game Replay System - API Routes
"""

import json
import time
from flask import Blueprint, request, jsonify, render_template
from database import get_db, ensure_db_exists

# Create Blueprint
api = Blueprint('api', __name__)
views = Blueprint('views', __name__)

# API Routes
@api.route('/record', methods=['POST'])
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
                from database import init_db
                init_db()
                return jsonify({'error': 'Database reinitialized, please retry'}), 503
            except Exception as init_error:
                print(f"Failed to reinitialize database: {init_error}")
        
        return jsonify({'error': str(e)}), 500

@api.route('/servers', methods=['GET'])
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

@api.route('/server/<server_id>/frames', methods=['GET'])
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

@api.route('/server/<server_id>/frame/<int:frame_number>', methods=['GET'])
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

@api.route('/health', methods=['GET'])
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
@views.route('/')
def index():
    """Serve the main replay viewer interface"""
    return render_template('index.html')

@views.route('/debug')
def debug():
    """Serve the debug interface for testing"""
    return render_template('debug.html') 