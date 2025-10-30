# WhisperFlow Auto-Start System - Task Hierarchy

**Timestamp:** 2025-10-18 15:30:00
**Phase:** 1 - Task Hierarchy Generation
**Status:** COMPLETED
**Agent:** ultrathink-engineer

---

## TASK HIERARCHY OVERVIEW

**Total L1 Milestones:** 7
**Total L2 Tasks:** 21
**Total L3 Micro-Tasks:** 38

**Estimated Completion:** 8 iterations (20% → 85%)

**Dependency Order:**
1. Docker Server Setup (foundational)
2. Docker Compose (orchestration)
3. systemd Service (client automation)
4. CLI Control Script (user interface)
5. Auto-Start Configuration (persistence)
6. Integration Testing (validation)
7. Resilience & Error Handling (robustness)
8. Logging & Monitoring (observability)

---

## L1 MILESTONE 1: Docker Server Setup

**Goal:** Modify Dockerfile for production port 8181 with optimized build

**Dependencies:** None (foundational)

**Success Criteria:**
- ✅ Dockerfile builds without errors
- ✅ Container uses port 8181
- ✅ Models NOT copied into image
- ✅ .dockerignore excludes unnecessary files

### L2 Task 1.1: Modify Dockerfile Port Configuration
**Description:** Change PORT from 8080 to 8181 in all occurrences

**L3 Micro-Tasks:**
- 1.1.1: Change `ENV PORT=8080` to `ENV PORT=8181` (line 5)
- 1.1.2: Change `EXPOSE 8080` to `EXPOSE 8181` (line 42)
- 1.1.3: Change CMD `--port 8080` to `--port 8181` (line 45)
- 1.1.4: Validate Dockerfile syntax with `docker build --check`

**Validation:**
```bash
grep -n "8181" Dockerfile  # Should show 3 lines
grep -n "8080" Dockerfile  # Should show 0 lines
```

### L2 Task 1.2: Optimize Dockerfile Build
**Description:** Remove model COPY to enable volume mount

**L3 Micro-Tasks:**
- 1.2.1: Comment out line 32: `# COPY whisperflow/models/*.pt /app/whisperflow/models/`
- 1.2.2: Keep `RUN mkdir -p /app/whisperflow/models` (line 29) for directory creation
- 1.2.3: Remove line 35: `RUN ls -la /app/whisperflow/models/` (no longer needed)
- 1.2.4: Update comment: "# Models will be mounted as volume at runtime"

**Validation:**
```bash
grep "COPY.*models" Dockerfile  # Should return nothing or commented line
```

### L2 Task 1.3: Create .dockerignore File
**Description:** Exclude unnecessary files from Docker build context

**L3 Micro-Tasks:**
- 1.3.1: Create .dockerignore in project root
- 1.3.2: Add patterns: `.venv/`, `.git/`, `*.pyc`, `__pycache__/`, `.pytest_cache/`, `*.log`
- 1.3.3: Add pattern: `.claude/` (documentation)
- 1.3.4: Validate with `docker build --no-cache` (should be faster)

**File Content:**
```
.venv/
.git/
.gitignore
*.pyc
__pycache__/
.pytest_cache/
*.log
.claude/
*.md
!README.md
```

**Validation:**
```bash
test -f .dockerignore && echo "✅ .dockerignore exists"
```

### L2 Task 1.4: Test Docker Build
**Description:** Validate Dockerfile builds successfully

**L3 Micro-Tasks:**
- 1.4.1: Run `docker build -t whisperflow-server:test .`
- 1.4.2: Validate build completes without errors
- 1.4.3: Inspect image: `docker inspect whisperflow-server:test | grep ExposedPorts`
- 1.4.4: Verify port 8181 exposed (not 8080)

**Validation:**
```bash
docker images | grep whisperflow-server
# Should show whisperflow-server:test
```

---

## L1 MILESTONE 2: Docker Compose Setup

**Goal:** Create orchestration file with health checks and volume mounts

**Dependencies:** L1 Milestone 1 (Dockerfile must be ready)

**Success Criteria:**
- ✅ docker-compose.yml exists and valid syntax
- ✅ Container starts with `docker-compose up -d`
- ✅ Health check passes
- ✅ Models mounted from host

### L2 Task 2.1: Create docker-compose.yml
**Description:** Define service configuration with all requirements

**L3 Micro-Tasks:**
- 2.1.1: Create docker-compose.yml in project root
- 2.1.2: Add service definition with build context
- 2.1.3: Configure port mapping 8181:8181
- 2.1.4: Add volume mount: `./whisperflow/models:/app/whisperflow/models:ro`
- 2.1.5: Add environment variable: `PORT=8181`
- 2.1.6: Configure restart policy: `unless-stopped`

**File Content:**
```yaml
version: '3.8'

services:
  whisperflow-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisperflow-server
    ports:
      - "8181:8181"
    volumes:
      - ./whisperflow/models:/app/whisperflow/models:ro
    environment:
      - PORT=8181
    restart: unless-stopped
```

**Validation:**
```bash
docker-compose config  # Validates YAML syntax
```

### L2 Task 2.2: Add Health Check Configuration
**Description:** Configure automatic health monitoring

**L3 Micro-Tasks:**
- 2.2.1: Add healthcheck section to service
- 2.2.2: Set test command: `curl -f http://localhost:8181/health`
- 2.2.3: Set interval: 10s, timeout: 5s, retries: 5
- 2.2.4: Set start_period: 30s (Whisper model load time)

**Updated Content:**
```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8181/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

**Validation:**
```bash
docker-compose up -d
docker ps  # Should show "healthy" in STATUS after 30s
```

### L2 Task 2.3: Test Container Startup
**Description:** Validate full startup workflow

**L3 Micro-Tasks:**
- 2.3.1: Run `docker-compose down` (clean slate)
- 2.3.2: Run `docker-compose up -d`
- 2.3.3: Monitor logs: `docker-compose logs -f` (expect model loading)
- 2.3.4: Wait for health check (max 60s)
- 2.3.5: Test health endpoint: `curl http://localhost:8181/health`
- 2.3.6: Verify response: HTTP 200 with JSON

**Validation:**
```bash
docker-compose ps | grep healthy
# Expected: whisperflow-server   Up (healthy)
```

### L2 Task 2.4: Verify Model Volume Mount
**Description:** Confirm models accessible inside container

**L3 Micro-Tasks:**
- 2.4.1: Execute into container: `docker exec -it whisperflow-server bash`
- 2.4.2: List models: `ls -lah /app/whisperflow/models/`
- 2.4.3: Verify files: small.pt, tiny.en.pt
- 2.4.4: Verify read-only: `touch /app/whisperflow/models/test.txt` (should fail)

**Validation:**
```bash
docker exec whisperflow-server ls /app/whisperflow/models/
# Expected: small.pt  tiny.en.pt
```

---

## L1 MILESTONE 3: systemd Service Setup

**Goal:** Create systemd service for client auto-start

**Dependencies:** L1 Milestone 2 (server must be ready)

**Success Criteria:**
- ✅ Service file valid syntax
- ✅ Service starts without errors
- ✅ Client connects to server
- ✅ WSL2 audio configured

### L2 Task 3.1: Create systemd Service File
**Description:** Define service configuration for client

**L3 Micro-Tasks:**
- 3.1.1: Create `whisperflow-client.service` in project root
- 3.1.2: Add [Unit] section with description and dependencies
- 3.1.3: Add [Service] section with user, working directory
- 3.1.4: Add environment variables for WSL2 audio
- 3.1.5: Add ExecStart with full path to .venv python
- 3.1.6: Add [Install] section with WantedBy=multi-user.target

**File Content:**
```ini
[Unit]
Description=WhisperFlow Universal Dictation Client
After=network.target docker.service
Wants=docker.service
Requires=network.target

[Service]
Type=simple
User=aseis
WorkingDirectory=/mnt/d/Dev/whisperflow-cloud
Environment="DISPLAY=:0"
Environment="PULSE_SERVER=unix:/mnt/wslg/PulseServer"
ExecStartPre=/bin/sleep 10
ExecStart=/mnt/d/Dev/whisperflow-cloud/.venv/bin/python /mnt/d/Dev/whisperflow-cloud/universal_dictation_client.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Validation:**
```bash
systemd-analyze verify whisperflow-client.service
# Should return no errors
```

### L2 Task 3.2: Create systemd Installation Script
**Description:** Script to install and enable service

**L3 Micro-Tasks:**
- 3.2.1: Create `install_systemd.sh` in project root
- 3.2.2: Detect current user dynamically: `whoami`
- 3.2.3: Replace {User} placeholder in service file
- 3.2.4: Copy service file to /etc/systemd/system/
- 3.2.5: Run `systemctl daemon-reload`
- 3.2.6: Enable service: `systemctl enable whisperflow-client`

**Script Content:**
```bash
#!/bin/bash
set -e

CURRENT_USER=$(whoami)
SERVICE_FILE="whisperflow-client.service"
INSTALL_PATH="/etc/systemd/system/$SERVICE_FILE"

echo "📦 Installing systemd service for user: $CURRENT_USER"

# Replace user placeholder
sed "s/User=aseis/User=$CURRENT_USER/g" $SERVICE_FILE > /tmp/$SERVICE_FILE

# Install service
sudo cp /tmp/$SERVICE_FILE $INSTALL_PATH
sudo systemctl daemon-reload

echo "✅ systemd service installed"
```

**Validation:**
```bash
bash install_systemd.sh
systemctl status whisperflow-client
# Should show "loaded" (not running yet)
```

### L2 Task 3.3: Test Manual Service Start
**Description:** Validate service can start manually

**L3 Micro-Tasks:**
- 3.3.1: Ensure Docker server is running: `docker-compose up -d`
- 3.3.2: Start service: `sudo systemctl start whisperflow-client`
- 3.3.3: Check status: `sudo systemctl status whisperflow-client`
- 3.3.4: Verify logs: `sudo journalctl -u whisperflow-client -n 50`
- 3.3.5: Look for "✅ Conectado al servidor WhisperFlow" in logs

**Validation:**
```bash
systemctl is-active whisperflow-client
# Expected: active
```

### L2 Task 3.4: Test Client Connection
**Description:** Verify WebSocket connection established

**L3 Micro-Tasks:**
- 3.4.1: Check client logs for connection message
- 3.4.2: Check server logs for WebSocket upgrade
- 3.4.3: Test hotkey: Press Ctrl+Space (should start recording)
- 3.4.4: Verify client logs show "🔴 Grabando..."

**Validation:**
```bash
sudo journalctl -u whisperflow-client -n 10 | grep "Conectado"
# Should show connection success message
```

---

## L1 MILESTONE 4: CLI Control Script

**Goal:** Create unified control interface for both components

**Dependencies:** L1 Milestone 2 (Docker Compose), L1 Milestone 3 (systemd)

**Success Criteria:**
- ✅ All subcommands work (start, stop, status, logs, restart)
- ✅ Dependency checks pass
- ✅ Error messages clear
- ✅ Script executable and in PATH

### L2 Task 4.1: Create Base CLI Script
**Description:** Implement script structure with argument parsing

**L3 Micro-Tasks:**
- 4.1.1: Create `whisperflow` file in project root (no extension)
- 4.1.2: Add shebang: `#!/bin/bash`
- 4.1.3: Set strict mode: `set -e`
- 4.1.4: Define PROJECT_DIR variable
- 4.1.5: Add usage function for help message
- 4.1.6: Add argument parsing with case statement

**Script Structure:**
```bash
#!/bin/bash
set -e

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
SERVICE_NAME="whisperflow-client"

usage() {
    echo "Usage: $0 {start|stop|status|logs|restart}"
    exit 1
}

case "$1" in
    start)   start_whisperflow ;;
    stop)    stop_whisperflow ;;
    status)  status_whisperflow ;;
    logs)    logs_whisperflow ;;
    restart) restart_whisperflow ;;
    *)       usage ;;
esac
```

### L2 Task 4.2: Implement Start Command
**Description:** Start Docker server + systemd client

**L3 Micro-Tasks:**
- 4.2.1: Create `start_whisperflow()` function
- 4.2.2: Print header: "🚀 Starting WhisperFlow..."
- 4.2.3: Start Docker: `docker-compose up -d`
- 4.2.4: Wait for health check (max 60s)
- 4.2.5: Start systemd: `sudo systemctl start whisperflow-client`
- 4.2.6: Print success: "✅ WhisperFlow started"

**Function Content:**
```bash
start_whisperflow() {
    echo "🚀 Starting WhisperFlow..."
    cd "$PROJECT_DIR"

    # Start Docker server
    docker-compose up -d

    # Wait for health check
    echo "⏳ Waiting for server to be healthy..."
    for i in {1..12}; do
        if curl -sf http://localhost:8181/health > /dev/null; then
            echo "✅ Server healthy"
            break
        fi
        sleep 5
    done

    # Start client
    sudo systemctl start "$SERVICE_NAME"
    sleep 2

    echo "✅ WhisperFlow started! (Ctrl+Space to dictate)"
}
```

### L2 Task 4.3: Implement Stop Command
**Description:** Stop both components gracefully

**L3 Micro-Tasks:**
- 4.3.1: Create `stop_whisperflow()` function
- 4.3.2: Stop systemd client first (graceful)
- 4.3.3: Stop Docker server: `docker-compose down`
- 4.3.4: Print success message

**Function Content:**
```bash
stop_whisperflow() {
    echo "🛑 Stopping WhisperFlow..."

    # Stop client first
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # Stop server
    cd "$PROJECT_DIR"
    docker-compose down

    echo "✅ WhisperFlow stopped"
}
```

### L2 Task 4.4: Implement Status Command
**Description:** Show status of both components

**L3 Micro-Tasks:**
- 4.4.1: Create `status_whisperflow()` function
- 4.4.2: Print section header for Docker
- 4.4.3: Run `docker-compose ps`
- 4.4.4: Print section header for systemd
- 4.4.5: Run `systemctl status whisperflow-client --no-pager`

**Function Content:**
```bash
status_whisperflow() {
    echo "📊 WhisperFlow Status:"
    echo ""
    echo "Docker Server:"
    cd "$PROJECT_DIR"
    docker-compose ps
    echo ""
    echo "systemd Client:"
    sudo systemctl status "$SERVICE_NAME" --no-pager || true
}
```

### L2 Task 4.5: Implement Logs Command
**Description:** Tail logs from both components

**L3 Micro-Tasks:**
- 4.5.1: Create `logs_whisperflow()` function
- 4.5.2: Start `docker-compose logs -f` in background
- 4.5.3: Start `journalctl -u whisperflow-client -f` in background
- 4.5.4: Setup trap to kill both on Ctrl+C
- 4.5.5: Wait for user interrupt

**Function Content:**
```bash
logs_whisperflow() {
    echo "📋 WhisperFlow Logs (Ctrl+C to exit):"
    echo ""

    cd "$PROJECT_DIR"
    docker-compose logs -f &
    DOCKER_PID=$!

    sudo journalctl -u "$SERVICE_NAME" -f &
    JOURNAL_PID=$!

    trap "kill $DOCKER_PID $JOURNAL_PID 2>/dev/null" EXIT
    wait
}
```

### L2 Task 4.6: Implement Restart Command
**Description:** Stop then start

**L3 Micro-Tasks:**
- 4.6.1: Create `restart_whisperflow()` function
- 4.6.2: Call `stop_whisperflow`
- 4.6.3: Sleep 2 seconds
- 4.6.4: Call `start_whisperflow`

**Function Content:**
```bash
restart_whisperflow() {
    stop_whisperflow
    sleep 2
    start_whisperflow
}
```

### L2 Task 4.7: Add Dependency Checks
**Description:** Validate prerequisites before execution

**L3 Micro-Tasks:**
- 4.7.1: Create `check_dependencies()` function
- 4.7.2: Check docker installed: `command -v docker`
- 4.7.3: Check docker-compose installed: `command -v docker-compose`
- 4.7.4: Check systemctl available: `command -v systemctl`
- 4.7.5: Call at script start (before case statement)

**Function Content:**
```bash
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Error: docker not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Error: docker-compose not installed"
        exit 1
    fi

    if ! command -v systemctl &> /dev/null; then
        echo "❌ Error: systemctl not available"
        exit 1
    fi
}
```

### L2 Task 4.8: Make Script Executable
**Description:** Set permissions and install to PATH

**L3 Micro-Tasks:**
- 4.8.1: Make executable: `chmod +x whisperflow`
- 4.8.2: Test local execution: `./whisperflow status`
- 4.8.3: Prepare for installation to /usr/local/bin/ (done in install.sh)

**Validation:**
```bash
test -x whisperflow && echo "✅ Script executable"
./whisperflow status  # Should show status
```

---

## L1 MILESTONE 5: Auto-Start Configuration

**Goal:** Enable automatic startup on WSL2 boot

**Dependencies:** All previous milestones (complete system)

**Success Criteria:**
- ✅ Docker container restarts automatically
- ✅ systemd service enabled
- ✅ install.sh runs successfully
- ✅ User in docker group

### L2 Task 5.1: Configure Docker Auto-Restart
**Description:** Update docker-compose.yml restart policy

**L3 Micro-Tasks:**
- 5.1.1: Verify `restart: unless-stopped` in docker-compose.yml
- 5.1.2: Test: `docker-compose up -d`
- 5.1.3: Verify container policy: `docker inspect whisperflow-server | grep RestartPolicy`
- 5.1.4: Expected: "Name": "unless-stopped"

**Validation:**
```bash
docker inspect whisperflow-server --format '{{.HostConfig.RestartPolicy.Name}}'
# Expected: unless-stopped
```

### L2 Task 5.2: Enable systemd Service
**Description:** Configure service to start on boot

**L3 Micro-Tasks:**
- 5.2.1: Enable service: `sudo systemctl enable whisperflow-client`
- 5.2.2: Verify enabled: `systemctl is-enabled whisperflow-client`
- 5.2.3: Check symlink created in /etc/systemd/system/multi-user.target.wants/

**Validation:**
```bash
systemctl is-enabled whisperflow-client
# Expected: enabled
```

### L2 Task 5.3: Create Installation Script
**Description:** Unified installation process

**L3 Micro-Tasks:**
- 5.3.1: Create `install.sh` in project root
- 5.3.2: Add dependency checks (docker, systemctl)
- 5.3.3: Add user to docker group check
- 5.3.4: Call install_systemd.sh script
- 5.3.5: Enable systemd service
- 5.3.6: Copy CLI script to /usr/local/bin/
- 5.3.7: Build Docker image
- 5.3.8: Print success message with usage instructions

**Script Content:**
```bash
#!/bin/bash
set -e

echo "🔧 Installing WhisperFlow Auto-Start System..."

# Check dependencies
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed. Install first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not installed. Install first."
    exit 1
fi

# Check user in docker group
if ! groups | grep -q docker; then
    echo "Adding user to docker group..."
    sudo usermod -aG docker $USER
    echo "⚠️ Logout and login again for docker group to take effect"
fi

# Validate models exist
if ! ls whisperflow/models/*.pt &> /dev/null; then
    echo "❌ Whisper models not found in whisperflow/models/"
    exit 1
fi
echo "✅ Whisper models found: $(ls whisperflow/models/*.pt | wc -l) files"

# Install systemd service
echo "Installing systemd service..."
bash install_systemd.sh
sudo systemctl enable whisperflow-client
echo "✅ systemd service enabled"

# Install CLI tool
echo "Installing CLI tool..."
sudo cp whisperflow /usr/local/bin/
sudo chmod +x /usr/local/bin/whisperflow
echo "✅ CLI tool installed"

# Build Docker image
echo "Building Docker image..."
docker-compose build
echo "✅ Docker image built"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  whisperflow start   - Start WhisperFlow"
echo "  whisperflow stop    - Stop WhisperFlow"
echo "  whisperflow status  - Check status"
echo "  whisperflow logs    - View logs"
echo ""
echo "Auto-start enabled. WhisperFlow will start on WSL2 boot."
```

**Validation:**
```bash
bash install.sh
# Should complete without errors
which whisperflow
# Expected: /usr/local/bin/whisperflow
```

### L2 Task 5.4: Test Auto-Start
**Description:** Validate startup on WSL2 reboot

**L3 Micro-Tasks:**
- 5.4.1: Run `whisperflow stop` (clean state)
- 5.4.2: Exit WSL2: `exit`
- 5.4.3: Shutdown WSL2: `wsl.exe --shutdown` (from PowerShell)
- 5.4.4: Wait 10 seconds
- 5.4.5: Reopen WSL2 terminal
- 5.4.6: Check status: `whisperflow status`
- 5.4.7: Expect both components running

**Validation:**
```bash
# After WSL2 reboot
whisperflow status
# Expected: Server Up, Client active (running)
```

---

## L1 MILESTONE 6: Integration Testing

**Goal:** Validate end-to-end workflows and resilience

**Dependencies:** All previous milestones (complete system)

**Success Criteria:**
- ✅ Full workflow passes (start → dictate → stop)
- ✅ Resilience tests pass (crash recovery)
- ✅ Backward compatibility preserved

### L2 Task 6.1: End-to-End Workflow Test
**Description:** Test complete user journey

**L3 Micro-Tasks:**
- 6.1.1: Start system: `whisperflow start`
- 6.1.2: Wait for ready message
- 6.1.3: Open text editor (VS Code or notepad)
- 6.1.4: Press Ctrl+Space, speak test phrase
- 6.1.5: Press Ctrl+Space again (stop)
- 6.1.6: Verify text appears in editor
- 6.1.7: Stop system: `whisperflow stop`

**Validation:**
```bash
# Manual test
# Expected: Text "This is a test" appears in editor after dictation
```

### L2 Task 6.2: Server Crash Recovery Test
**Description:** Validate client reconnection

**L3 Micro-Tasks:**
- 6.2.1: Start system: `whisperflow start`
- 6.2.2: Kill Docker container: `docker kill whisperflow-server`
- 6.2.3: Wait 10 seconds (Docker restarts automatically)
- 6.2.4: Check client logs for reconnection attempts
- 6.2.5: Verify client reconnects after server restart
- 6.2.6: Test dictation still works

**Validation:**
```bash
docker ps | grep whisperflow-server
# Should show restarted container
journalctl -u whisperflow-client -n 20 | grep "Conectado"
# Should show reconnection message
```

### L2 Task 6.3: Client Restart Test
**Description:** Validate client can restart independently

**L3 Micro-Tasks:**
- 6.3.1: Start system: `whisperflow start`
- 6.3.2: Stop client: `sudo systemctl stop whisperflow-client`
- 6.3.3: Wait 5 seconds
- 6.3.4: Start client: `sudo systemctl start whisperflow-client`
- 6.3.5: Verify client reconnects to server
- 6.3.6: Test dictation works

**Validation:**
```bash
systemctl is-active whisperflow-client
# Expected: active
```

### L2 Task 6.4: Backward Compatibility Test
**Description:** Ensure old scripts still work

**L3 Micro-Tasks:**
- 6.4.1: Stop new system: `whisperflow stop`
- 6.4.2: Run old script: `bash start_dictado.sh`
- 6.4.3: Verify server starts on port 8181
- 6.4.4: Verify client connects
- 6.4.5: Test dictation works
- 6.4.6: Stop with Ctrl+C

**Validation:**
```bash
# start_dictado.sh should work identically to before
# No errors, no regressions
```

---

## L1 MILESTONE 7: Resilience & Error Handling

**Goal:** Add reconnection logic and error recovery

**Dependencies:** L1 Milestone 3 (client code)

**Success Criteria:**
- ✅ Client has reconnection logic with exponential backoff
- ✅ Max retries configured (5 attempts)
- ✅ Connection failures logged clearly

### L2 Task 7.1: Add Client Reconnection Logic
**Description:** Modify universal_dictation_client.py

**L3 Micro-Tasks:**
- 7.1.1: Read current `connect_to_server()` method
- 7.1.2: Add `max_retries` parameter (default 5)
- 7.1.3: Wrap connection in retry loop
- 7.1.4: Add exponential backoff: `wait = 2 ** attempt`
- 7.1.5: Add logging for each retry attempt
- 7.1.6: Return success/failure boolean

**Code Changes:**
```python
async def connect_to_server(self, max_retries=5):
    """Conecta al servidor WhisperFlow con retry logic"""
    for attempt in range(max_retries):
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            print("✅ Conectado al servidor WhisperFlow")
            asyncio.create_task(self.listen_transcriptions())
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # exponential backoff
                print(f"⚠️ Intento {attempt+1}/{max_retries} falló. Reintentando en {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Error conectando después de {max_retries} intentos: {e}")
                self.is_connected = False
                return False
```

**Validation:**
- Test with server offline → Should retry 5 times
- Test with server online → Should connect on first try

### L2 Task 7.2: Add Automatic Reconnection on Disconnect
**Description:** Reconnect if connection lost during operation

**L3 Micro-Tasks:**
- 7.2.1: Modify `listen_transcriptions()` method
- 7.2.2: Catch `ConnectionClosed` exception
- 7.2.3: Call `connect_to_server()` to retry
- 7.2.4: Log reconnection attempts

**Code Changes:**
```python
async def listen_transcriptions(self):
    """Escucha las transcripciones del servidor"""
    try:
        async for message in self.websocket:
            data = json.loads(message)
            # ... existing code ...
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Conexión perdida. Reintentando...")
        self.is_connected = False
        await asyncio.sleep(2)
        await self.connect_to_server()  # Retry connection
    except Exception as e:
        print(f"❌ Error: {e}")
```

**Validation:**
- Kill server while client running → Client should reconnect automatically

### L2 Task 7.3: Test Reconnection Logic
**Description:** Validate all reconnection scenarios

**L3 Micro-Tasks:**
- 7.3.1: Test scenario: Server offline at client start
- 7.3.2: Test scenario: Server crashes during dictation
- 7.3.3: Test scenario: Network interruption
- 7.3.4: Verify logs show retry attempts
- 7.3.5: Verify max retries respected

**Validation:**
```bash
# Scenario 1: Server offline
whisperflow stop
sudo systemctl start whisperflow-client
# Client should retry 5 times, then give up

# Scenario 2: Server crash
whisperflow start
docker kill whisperflow-server
# Client should reconnect when server restarts
```

---

## L1 MILESTONE 8: Logging & Monitoring

**Goal:** Configure comprehensive logging for troubleshooting

**Dependencies:** L1 Milestone 2 (Docker), L1 Milestone 3 (systemd)

**Success Criteria:**
- ✅ Docker logs accessible via CLI
- ✅ systemd logs in journald
- ✅ `whisperflow logs` command works

### L2 Task 8.1: Configure Docker Logging
**Description:** Add logging configuration to docker-compose.yml

**L3 Micro-Tasks:**
- 8.1.1: Add logging section to service
- 8.1.2: Set driver: json-file
- 8.1.3: Set max-size: 10m
- 8.1.4: Set max-file: 3
- 8.1.5: Test log rotation

**Configuration:**
```yaml
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

**Validation:**
```bash
docker inspect whisperflow-server | grep LogConfig
# Should show json-file with max-size
```

### L2 Task 8.2: Validate systemd Logging
**Description:** Confirm journald capturing client logs

**L3 Micro-Tasks:**
- 8.2.1: Verify `StandardOutput=journal` in service file
- 8.2.2: Verify `StandardError=journal` in service file
- 8.2.3: Test log access: `journalctl -u whisperflow-client -n 50`
- 8.2.4: Test real-time tail: `journalctl -u whisperflow-client -f`

**Validation:**
```bash
journalctl -u whisperflow-client --no-pager | tail -n 20
# Should show recent client logs
```

### L2 Task 8.3: Test Unified Logs Command
**Description:** Validate `whisperflow logs` shows both sources

**L3 Micro-Tasks:**
- 8.3.1: Start system: `whisperflow start`
- 8.3.2: Run: `whisperflow logs`
- 8.3.3: Verify Docker logs appear
- 8.3.4: Verify systemd logs appear
- 8.3.5: Verify Ctrl+C stops tail cleanly

**Validation:**
```bash
# whisperflow logs should show interleaved logs from both components
# Should be readable and useful for debugging
```

---

## TASK COMPLETION TRACKING

### Progress Calculation

**Formula:**
```
Progress % = (Completed L3 Tasks / Total L3 Tasks) * 100
```

**Total L3 Tasks:** 38

**Progress Milestones:**
- 0 tasks: 0% (Phase 0 - Analysis)
- 4 tasks: 10% (Phase 1 - Task Hierarchy)
- 8 tasks: 20% (Iteration 1 - Docker Foundation)
- 13 tasks: 30% (Iteration 2 - Docker Compose)
- 18 tasks: 40% (Iteration 3 - systemd Service)
- 24 tasks: 50% (Iteration 4 - CLI Script)
- 28 tasks: 60% (Iteration 5 - Auto-Start)
- 31 tasks: 70% (Iteration 6 - Integration Tests)
- 34 tasks: 80% (Iteration 7 - Resilience)
- 38 tasks: 85% (Iteration 8 - Logging)
- Integration: 90% (Phase 9)
- Final Report: 100% (Phase 10)

### Iteration Mapping

**Iteration 1 (20%):** L1 Milestone 1 - Docker Server Setup
- L3 Tasks: 1.1.1 → 1.4.4 (8 tasks)

**Iteration 2 (30%):** L1 Milestone 2 - Docker Compose
- L3 Tasks: 2.1.1 → 2.4.4 (13 tasks total, 5 new)

**Iteration 3 (40%):** L1 Milestone 3 - systemd Service
- L3 Tasks: 3.1.1 → 3.4.4 (18 tasks total, 5 new)

**Iteration 4 (50%):** L1 Milestone 4 - CLI Script
- L3 Tasks: 4.1.1 → 4.8.3 (24 tasks total, 6 new)

**Iteration 5 (60%):** L1 Milestone 5 - Auto-Start
- L3 Tasks: 5.1.1 → 5.4.7 (28 tasks total, 4 new)

**Iteration 6 (70%):** L1 Milestone 6 - Integration Testing
- L3 Tasks: 6.1.1 → 6.4.6 (31 tasks total, 3 new)

**Iteration 7 (80%):** L1 Milestone 7 - Resilience
- L3 Tasks: 7.1.1 → 7.3.5 (34 tasks total, 3 new)

**Iteration 8 (85%):** L1 Milestone 8 - Logging
- L3 Tasks: 8.1.1 → 8.3.5 (38 tasks total, 4 new)

---

## DEPENDENCY GRAPH

```
Iteration 1 (Docker Server)
    ↓
Iteration 2 (Docker Compose)
    ↓
Iteration 3 (systemd Service)
    ↓
Iteration 4 (CLI Script)
    ↓
Iteration 5 (Auto-Start)
    ↓
Iteration 6 (Integration Tests)
    ↙            ↘
Iteration 7      Iteration 8
(Resilience)     (Logging)
    ↘            ↙
    Phase 9 (Integration 90%)
         ↓
    Phase 10 (Final Report 100%)
```

**Critical Path:** 1 → 2 → 3 → 4 → 5 → 6 → 7/8 → 9 → 10

**Parallelizable:** Iterations 7 & 8 (can be done simultaneously)

---

## QUALITY GATES

Each iteration must pass quality gates before proceeding:

**Iteration 1 Gate:**
- ✅ Dockerfile builds without errors
- ✅ Port 8181 exposed (not 8080)
- ✅ .dockerignore exists

**Iteration 2 Gate:**
- ✅ docker-compose.yml valid syntax
- ✅ Container starts and becomes healthy
- ✅ Models mounted correctly

**Iteration 3 Gate:**
- ✅ Service file valid syntax
- ✅ Service starts without errors
- ✅ Client connects to server

**Iteration 4 Gate:**
- ✅ All CLI subcommands work
- ✅ Script executable
- ✅ Dependency checks pass

**Iteration 5 Gate:**
- ✅ install.sh completes successfully
- ✅ systemd service enabled
- ✅ CLI in /usr/local/bin/

**Iteration 6 Gate:**
- ✅ End-to-end dictation works
- ✅ Backward compatibility preserved
- ✅ Crash recovery works

**Iteration 7 Gate:**
- ✅ Reconnection logic tested
- ✅ Max retries respected
- ✅ Exponential backoff working

**Iteration 8 Gate:**
- ✅ Logs accessible via CLI
- ✅ Log rotation configured
- ✅ Useful debugging info

---

## PHASE 1 COMPLETION SUMMARY

**Deliverables:**
- ✅ Task hierarchy (7 L1, 21 L2, 38 L3 tasks)
- ✅ Iteration plan (8 iterations)
- ✅ Dependency graph
- ✅ Quality gates defined
- ✅ Progress calculation formula

**Next Phase:** Phase 2-8 (Iterative Execution 20% → 85%)

**Estimated Time:** 8 iterations × 10-15 min = 80-120 minutes total

**Status:** Phase 1 COMPLETE (10% → 20% ready to start)

---

**Agent:** ultrathink-engineer
**Project:** whisperflow-cloud
**Timestamp:** 2025-10-18 15:30:00
