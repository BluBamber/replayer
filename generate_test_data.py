#!/usr/bin/env python3
"""
ROBLOX Game Replay System - Test Data Generator
This script creates a fake server with animated frame data for testing
"""

import json
import random
import time
import uuid
import math
from database import get_db, ensure_db_exists

# Configuration
FRAMES_COUNT = 100
SERVER_ID = f"test-server-{uuid.uuid4()}"
PLACE_ID = 12345678
GAME_NAME = "Test Game"
CREATOR_ID = 87654321

# Object counts
PLAYER_COUNT = 3
PARTS_COUNT = 20

def generate_color():
    """Generate a random color"""
    return {
        "R": random.random(),
        "G": random.random(),
        "B": random.random()
    }

def generate_vector3():
    """Generate a random position vector"""
    return {
        "X": random.uniform(-50, 50),
        "Y": random.uniform(0, 20),
        "Z": random.uniform(-50, 50)
    }

def animate_position(base_pos, frame_num, amplitude=10, frequency=0.02):
    """Generate an animated position based on frame number"""
    x = base_pos["X"] + amplitude * math.sin(frame_num * frequency)
    y = base_pos["Y"] + amplitude * 0.2 * math.sin(frame_num * frequency * 2)
    z = base_pos["Z"] + amplitude * math.cos(frame_num * frequency)
    return {"X": x, "Y": y, "Z": z}

def generate_rotation():
    """Generate a random rotation in degrees"""
    return {
        "X": random.uniform(0, 360),
        "Y": random.uniform(0, 360),
        "Z": random.uniform(0, 360)
    }

def animate_rotation(base_rot, frame_num, speed=2):
    """Generate an animated rotation based on frame number"""
    x = (base_rot["X"] + frame_num * speed) % 360
    y = (base_rot["Y"] + frame_num * speed * 0.5) % 360
    z = (base_rot["Z"] + frame_num * speed * 0.3) % 360
    return {"X": x, "Y": y, "Z": z}

def generate_size():
    """Generate a random size"""
    return {
        "X": random.uniform(1, 5),
        "Y": random.uniform(1, 5),
        "Z": random.uniform(1, 5)
    }

def generate_player_base(player_index):
    """Generate base player data"""
    names = ["Player1", "Player2", "Player3", "Player4", "Player5"]
    return {
        "Name": names[player_index % len(names)],
        "UserId": 1000 + player_index,
        "BasePosition": generate_vector3()
    }

def generate_part_base(part_index):
    """Generate base part data"""
    materials = ["Plastic", "Wood", "Metal", "Neon"]
    return {
        "Name": f"Part{part_index}",
        "FullPath": f"Workspace.Part{part_index}",
        "BasePosition": generate_vector3(),
        "BaseRotation": generate_rotation(),
        "Size": generate_size(),
        "Material": random.choice(materials),
        "Color": generate_color(),
        "Transparency": random.uniform(0, 0.5) if random.random() > 0.8 else 0
    }

def generate_frame_data(frame_number, player_bases, part_bases):
    """Generate frame data for a specific frame"""
    # Generate player data
    players = []
    for i, player_base in enumerate(player_bases):
        player = {
            "Name": player_base["Name"],
            "UserId": player_base["UserId"],
            "Position": animate_position(player_base["BasePosition"], frame_number)
        }
        players.append(player)
    
    # Generate part data
    parts = []
    for i, part_base in enumerate(part_bases):
        part = {
            "Name": part_base["Name"],
            "FullPath": part_base["FullPath"],
            "Position": animate_position(part_base["BasePosition"], frame_number),
            "Rotation": animate_rotation(part_base["BaseRotation"], frame_number),
            "Size": part_base["Size"],
            "Material": part_base["Material"],
            "Color": part_base["Color"],
            "Transparency": part_base["Transparency"]
        }
        parts.append(part)
    
    # Game info
    game_info = {
        "PlaceId": PLACE_ID,
        "GameName": GAME_NAME,
        "CreatorId": CREATOR_ID
    }
    
    return {
        "players": players,
        "parts": parts,
        "game_info": game_info
    }

def main():
    """Main function to generate and store test data"""
    print(f"Starting test data generation for {FRAMES_COUNT} frames...")
    
    # Ensure database exists
    ensure_db_exists()
    conn = get_db()
    cursor = conn.cursor()
    
    # Register server
    print(f"Registering test server: {SERVER_ID}")
    cursor.execute('''
        INSERT OR REPLACE INTO servers (server_id, place_id, creator_id, game_name)
        VALUES (?, ?, ?, ?)
    ''', (SERVER_ID, PLACE_ID, CREATOR_ID, GAME_NAME))
    conn.commit()
    
    # Generate base data for players and parts
    player_bases = [generate_player_base(i) for i in range(PLAYER_COUNT)]
    part_bases = [generate_part_base(i) for i in range(PARTS_COUNT)]
    
    # Create ground part
    ground = {
        "Name": "Ground",
        "FullPath": "Workspace.Ground",
        "BasePosition": {"X": 0, "Y": 0, "Z": 0},
        "BaseRotation": {"X": 0, "Y": 0, "Z": 0},
        "Size": {"X": 100, "Y": 1, "Z": 100},
        "Material": "Plastic",
        "Color": {"R": 0.3, "G": 0.7, "B": 0.3},
        "Transparency": 0
    }
    part_bases.append(ground)
    
    # Generate frames
    start_time = time.time()
    base_timestamp = start_time
    
    print("Generating frames...")
    for frame in range(FRAMES_COUNT):
        # Generate frame data
        frame_data = generate_frame_data(frame, player_bases, part_bases)
        
        # Current timestamp (speed up time for the simulation)
        timestamp = base_timestamp + (frame * 0.1)  # 10 FPS in simulated time
        
        # Store frame in database
        cursor.execute('''
            INSERT INTO frames (server_id, frame_number, timestamp, parts_data, players_data, game_info)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            SERVER_ID, 
            frame, 
            timestamp, 
            json.dumps(frame_data["parts"]), 
            json.dumps(frame_data["players"]), 
            json.dumps(frame_data["game_info"])
        ))
        
        # Update server last frame
        cursor.execute('''
            UPDATE servers SET last_frame = ? WHERE server_id = ?
        ''', (frame, SERVER_ID))
        
        if frame % 10 == 0:
            print(f"Generated frame {frame}/{FRAMES_COUNT}")
    
    # Commit all changes
    conn.commit()
    conn.close()
    
    elapsed_time = time.time() - start_time
    print(f"Test data generation complete! Created {FRAMES_COUNT} frames in {elapsed_time:.2f} seconds")
    print(f"Server ID: {SERVER_ID}")
    print("You can now view the replay in your browser")

if __name__ == "__main__":
    main() 