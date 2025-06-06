// Three.js scene setup
let scene, camera, renderer;
let gameData = [];
let currentFrame = 0;
let isPlaying = false;
let playbackFPS = 30; // Default to 30 FPS
let parts = new Map();
let players = new Map();
let currentServerId = null;
let isReplayLoaded = false;

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
    // Create a group to hold the player parts
    const playerGroup = new THREE.Group();
    
    // Create body (cylinder)
    const bodyGeometry = new THREE.CylinderGeometry(1, 1, 4, 8);
    const bodyMaterial = new THREE.MeshLambertMaterial({ color: 0x00ff00 });
    const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
    body.position.y = 2; // Center the body vertically
    playerGroup.add(body);
    
    // Create head (sphere)
    const headGeometry = new THREE.SphereGeometry(1, 8, 8);
    const headMaterial = new THREE.MeshLambertMaterial({ color: 0x00ff00 });
    const head = new THREE.Mesh(headGeometry, headMaterial);
    head.position.y = 4; // Position head on top of body
    playerGroup.add(head);
    
    // Position the entire player group
    playerGroup.position.set(
        playerData.Position.X,
        playerData.Position.Y,
        playerData.Position.Z
    );
    
    playerGroup.userData = { name: playerData.Name, userId: playerData.UserId };
    
    return playerGroup;
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
    document.getElementById('frameSlider').value = frameData.frame;
}

// API functions
async function loadServers() {
    try {
        console.log("Loading servers...");
        const response = await fetch('/api/servers');
        const servers = await response.json();
        console.log(`Loaded ${servers.length} servers`);
        
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
        console.log(`Loading data for server: ${serverId}`);
        document.getElementById('loading').style.display = 'block';
        
        const response = await fetch(`/api/server/${serverId}/frames`);
        const frames = await response.json();
        
        console.log('Server data loaded:', frames.length, 'frames');
        console.log('First frame data:', frames[0]);
        
        gameData = frames;
        currentFrame = 0;
        currentServerId = serverId;
        
        console.log(`Loaded ${frames.length} frames`);
        document.getElementById('loading').style.display = 'none';
        
        if (frames.length > 0) {
            document.getElementById('totalFrames').textContent = frames.length;
            document.getElementById('frameSlider').max = frames.length - 1;
            document.getElementById('currentServer').textContent = serverId;
            
            if (frames[0].gameInfo && frames[0].gameInfo.PlaceId) {
                document.getElementById('gameName').textContent = `Place ${frames[0].gameInfo.PlaceId}`;
            }
            
            renderFrame(frames[0]);
            isReplayLoaded = true;
            
            console.log('Enabling controls...');
            // Enable controls now that data is loaded
            document.getElementById('playPause').disabled = false;
            document.getElementById('prevFrame').disabled = false;
            document.getElementById('nextFrame').disabled = false;
            document.getElementById('frameSlider').disabled = false;
            document.getElementById('speedControl').disabled = false;
            
            console.log('Controls enabled:', {
                playPause: !document.getElementById('playPause').disabled,
                prevFrame: !document.getElementById('prevFrame').disabled,
                nextFrame: !document.getElementById('nextFrame').disabled,
                frameSlider: !document.getElementById('frameSlider').disabled,
                speedControl: !document.getElementById('speedControl').disabled
            });
            
            return true;
        }
        
        return false;
    } catch (error) {
        console.error('Failed to load server data:', error);
        document.getElementById('loading').style.display = 'none';
        return false;
    }
}

// Control functions
function playPause() {
    if (!isReplayLoaded) {
        console.log("Cannot play/pause: No replay loaded");
        return;
    }
    
    console.log("Toggling play state from:", isPlaying, "to:", !isPlaying);
    isPlaying = !isPlaying;
    document.getElementById('playPause').textContent = isPlaying ? 'Pause' : 'Play';
    console.log(`Playback: ${isPlaying ? 'Playing' : 'Paused'}`);
    
    if (isPlaying) {
        console.log("Starting play loop");
        playLoop();
    }
}

function playLoop() {
    if (!isPlaying) {
        console.log("Play loop stopped: isPlaying is false");
        return;
    }
    
    if (currentFrame >= gameData.length - 1) {
        console.log("Reached end of replay, stopping playback");
        isPlaying = false;
        document.getElementById('playPause').textContent = 'Play';
        return;
    }
    
    currentFrame++;
    console.log("Playing frame:", currentFrame);
    renderFrame(gameData[currentFrame]);
    
    // Calculate delay based on FPS
    const frameDelay = 1000 / playbackFPS;
    setTimeout(playLoop, frameDelay);
}

function nextFrame() {
    if (!isReplayLoaded) {
        console.log("Cannot advance: No replay loaded");
        return;
    }
    
    if (currentFrame < gameData.length - 1) {
        currentFrame++;
        renderFrame(gameData[currentFrame]);
        console.log(`Advanced to frame ${currentFrame}`);
    }
}

function prevFrame() {
    if (!isReplayLoaded) {
        console.log("Cannot go back: No replay loaded");
        return;
    }
    
    if (currentFrame > 0) {
        currentFrame--;
        renderFrame(gameData[currentFrame]);
        console.log(`Went back to frame ${currentFrame}`);
    }
}

function resetCamera() {
    cameraControls.distance = 100;
    cameraControls.phi = Math.PI / 4;
    cameraControls.theta = 0;
    updateCamera();
    console.log("Camera reset");
}

// Event listeners
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Page loaded");
    initScene();
    
    // Load available servers
    await loadServers();
    
    // Hide loading indicator
    document.getElementById('loading').style.display = 'none';
    
    // Disable controls until data is loaded
    document.getElementById('playPause').disabled = true;
    document.getElementById('prevFrame').disabled = true;
    document.getElementById('nextFrame').disabled = true;
    document.getElementById('frameSlider').disabled = true;
    document.getElementById('speedControl').disabled = true;
    
    console.log('Initial control state:', {
        playPause: !document.getElementById('playPause').disabled,
        prevFrame: !document.getElementById('prevFrame').disabled,
        nextFrame: !document.getElementById('nextFrame').disabled,
        frameSlider: !document.getElementById('frameSlider').disabled,
        speedControl: !document.getElementById('speedControl').disabled
    });
    
    // Setup controls
    document.getElementById('loadServer').addEventListener('click', async () => {
        const serverId = document.getElementById('serverSelect').value;
        console.log("Loading server:", serverId);
        
        if (serverId) {
            await loadServerData(serverId);
        } else {
            console.log("No server selected");
        }
    });
    
    document.getElementById('playPause').addEventListener('click', () => {
        console.log("Play/Pause clicked, isReplayLoaded:", isReplayLoaded);
        playPause();
    });
    
    document.getElementById('nextFrame').addEventListener('click', () => {
        console.log("Next frame clicked, isReplayLoaded:", isReplayLoaded);
        nextFrame();
    });
    
    document.getElementById('prevFrame').addEventListener('click', () => {
        console.log("Previous frame clicked, isReplayLoaded:", isReplayLoaded);
        prevFrame();
    });
    
    document.getElementById('resetCamera').addEventListener('click', resetCamera);
    
    document.getElementById('frameSlider').addEventListener('input', (e) => {
        if (!isReplayLoaded) {
            console.log("Frame slider changed but replay not loaded");
            return;
        }
        
        currentFrame = parseInt(e.target.value);
        console.log("Frame slider changed to:", currentFrame);
        if (gameData[currentFrame]) {
            renderFrame(gameData[currentFrame]);
        }
    });
    
    document.getElementById('speedControl').addEventListener('change', (e) => {
        playbackFPS = parseInt(e.target.value);
        console.log("FPS changed to:", playbackFPS);
    });
    
    console.log("UI initialized, ready for user interaction");
});

// Handle window resize
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}); 