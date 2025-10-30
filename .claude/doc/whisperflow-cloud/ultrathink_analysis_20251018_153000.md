# WhisperFlow Auto-Start System - Reverse Engineering Analysis

**Timestamp:** 2025-10-18 15:30:00
**Phase:** 0 - Reverse Engineer & Analysis
**Status:** COMPLETED
**Agent:** ultrathink-engineer

---

## 1. CURRENT ARCHITECTURE

### 1.1 Current Manual Workflow

**Terminal 1: Server**
```bash
source .venv/bin/activate
uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port 8181
```

**Terminal 2: Client**
```bash
source .venv/bin/activate
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"
python universal_dictation_client.py
```

**Pain Points:**
- Requires 2 terminal windows
- Manual activation of virtual environment (2x)
- Manual WSL2 audio configuration
- No automatic startup on WSL2 boot
- No centralized control (start/stop/status)

### 1.2 Current Files Inventory

**Dockerfile:**
- Location: `/mnt/d/Dev/whisperflow-cloud/Dockerfile`
- Base image: `python:3.10-slim`
- Current port: **8080** (DISCREPANCY - needs to be 8181)
- Model handling: Explicitly copies `whisperflow/models/*.pt` to container
- CMD: `uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port 8080`
- Issues found:
  - ❌ Port mismatch (8080 vs 8181)
  - ❌ Models copied INTO container (large, slow rebuilds)
  - ✅ System dependencies installed correctly

**start_dictado.sh:**
- Location: `/mnt/d/Dev/whisperflow-cloud/start_dictado.sh`
- Port used: **8181** (correct)
- Features:
  - ✅ Activates .venv
  - ✅ WSL2 audio config (DISPLAY=:0, PULSE_SERVER)
  - ✅ Health check with retry (12 attempts, 60s timeout)
  - ✅ Cleanup function with trap
  - ✅ Background server execution
- Workflow:
  1. Start server in background
  2. Wait for health check
  3. Start client in foreground
  4. Cleanup on exit (pkill processes)

**universal_dictation_client.py:**
- Location: `/mnt/d/Dev/whisperflow-cloud/universal_dictation_client.py`
- Server URL: `ws://localhost:8181/ws` (correct)
- Dependencies:
  - PyAudio (microphone capture)
  - pynput (keyboard hotkeys + text insertion)
  - pyperclip (clipboard operations)
  - websockets (WebSocket client)
- Hotkey: Ctrl+Space (toggle recording)
- **CRITICAL FINDING:** NO automatic reconnection logic
  - `connect_to_server()` only tries once
  - If server dies, client remains disconnected
  - **MUST ADD:** Retry logic with exponential backoff

**Whisper Models:**
- Location: `/mnt/d/Dev/whisperflow-cloud/whisperflow/models/`
- Files found:
  - `small.pt` (462MB)
  - `tiny.en.pt` (73MB)
- Decision: Mount as Docker volume (avoid copying into image)

### 1.3 Port Configuration Analysis

**Current State:**
- Dockerfile: PORT 8080 ❌
- start_dictado.sh: PORT 8181 ✅
- universal_dictation_client.py: PORT 8181 ✅

**Decision:** Standardize on **PORT 8181** (production port)

**Action Required:**
- Update Dockerfile ENV PORT=8181
- Update Dockerfile CMD to use 8181
- Update EXPOSE directive to 8181

---

## 2. DEPENDENCY GRAPH

```
┌──────────────────────────┐
│   Docker Container       │
│   (WhisperFlow Server)   │
│   Port: 8181             │
│   Health: /health        │
└────────┬─────────────────┘
         │
         │ WebSocket (ws://localhost:8181/ws)
         │
         ▼
┌──────────────────────────┐
│   systemd Service        │
│   (Dictation Client)     │
│   - PyAudio (mic)        │
│   - pynput (keyboard)    │
│   - WSL2 audio env       │
└──────────────────────────┘

Dependencies:
1. Docker must start BEFORE systemd client
2. Client waits for server health check
3. Client reconnects if server restarts
```

**Critical Path:**
1. Docker Compose starts server container
2. Container loads Whisper model (~30s)
3. Health check passes (HTTP 200 on /health)
4. systemd starts client service
5. Client connects to WebSocket
6. User can press Ctrl+Space to dictate

**Failure Modes:**
- Server crashes → Client must reconnect (MISSING)
- WSL2 reboot → Both must auto-start
- Audio device unavailable → Client should retry
- Model missing → Server fails to start (Docker volume critical)

---

## 3. CONSTRAINT ANALYSIS

### 3.1 Why Client CANNOT be in Docker

**PyAudio (Microphone Access):**
- Requires direct access to `/dev/snd/*` devices
- Docker would need: `--device /dev/snd`
- WSL2 audio routing through PulseAudio is fragile in containers

**pynput (Keyboard Hotkeys):**
- Requires access to X11/Wayland display server
- Needs to capture GLOBAL hotkeys (Ctrl+Space)
- Docker would need: `-e DISPLAY=:0 -v /tmp/.X11-unix`
- Would require `--privileged` for input event capture

**pynput (Text Insertion):**
- Simulates keyboard presses (Ctrl+V)
- Requires X11/Wayland access
- Must interact with active window (focus)

**Conclusion:** Client MUST run on host as systemd service.

### 3.2 WSL2 Audio Configuration

**Required Environment Variables:**
```bash
DISPLAY=:0
PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

**systemd Service File Requirements:**
- Environment= directives for both vars
- WorkingDirectory= to project root
- ExecStart= with full path to .venv python

**Validation:**
- Test with: `pactl info` (should show PulseAudio server)
- Test with: `arecord -l` (should list audio devices)

### 3.3 Docker Model Volume Strategy

**Current (BAD):**
```dockerfile
COPY whisperflow/models/*.pt /app/whisperflow/models/
```

**Problem:**
- 462MB copied into image every build
- Slow build times
- Wastes disk space (multiple image versions)

**Solution (GOOD):**
```yaml
volumes:
  - ./whisperflow/models:/app/whisperflow/models:ro
```

**Benefits:**
- Model files stay on host
- Fast rebuilds (no model copy)
- Single source of truth
- Read-only mount (safety)

### 3.4 Backward Compatibility

**Existing Scripts:**
- `start_dictado.sh` - Must continue working
- `run.sh` - Must continue working (if exists)
- Manual workflows - Users can still use them

**Strategy:**
- DO NOT modify existing scripts
- New system is ADDITIVE
- Users can choose: manual OR automated

---

## 4. TARGET ARCHITECTURE

### 4.1 Components to Create

**1. docker-compose.yml**
```yaml
services:
  whisperflow-server:
    build: .
    ports: ["8181:8181"]
    volumes: ["./whisperflow/models:/app/whisperflow/models:ro"]
    healthcheck: curl localhost:8181/health
    restart: unless-stopped
```

**2. whisperflow-client.service** (systemd)
```ini
[Unit]
Description=WhisperFlow Universal Dictation Client
After=docker.service

[Service]
User={CURRENT_USER}
WorkingDirectory=/mnt/d/Dev/whisperflow-cloud
Environment="DISPLAY=:0"
Environment="PULSE_SERVER=unix:/mnt/wslg/PulseServer"
ExecStart={PATH_TO_VENV}/python universal_dictation_client.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**3. whisperflow** (CLI control script)
```bash
#!/bin/bash
Commands:
- start: docker-compose up -d && systemctl start whisperflow-client
- stop: systemctl stop whisperflow-client && docker-compose down
- status: Show both components
- logs: Tail both logs
- restart: stop + start
```

**4. install.sh**
```bash
#!/bin/bash
Steps:
1. Check docker installed
2. Add user to docker group
3. Install systemd service
4. Enable systemd service (auto-start)
5. Copy CLI to /usr/local/bin
6. Build Docker image
7. Test health check
```

**5. .dockerignore**
```
.venv/
.git/
*.pyc
__pycache__/
.pytest_cache/
```

**6. Modified Dockerfile**
- Change PORT 8080 → 8181
- Remove COPY models line
- Update CMD to use 8181

**7. Client reconnection logic**
- Add retry loop in `connect_to_server()`
- Exponential backoff (2^attempt seconds)
- Max retries: 5
- Log connection attempts

### 4.2 Startup Flow

**One-Time Installation:**
```bash
./install.sh
```
Output:
- Docker Compose configured ✅
- systemd service installed ✅
- CLI tool in PATH ✅
- Auto-start enabled ✅

**Daily Usage:**
```bash
./whisperflow start
```
Flow:
1. Docker Compose starts server container (detached)
2. Container loads Whisper model (~30s)
3. Health check waits for server ready
4. systemd starts client service
5. Client connects to WebSocket
6. Ctrl+Space hotkey active

**Status Check:**
```bash
./whisperflow status
```
Output:
- Docker server: RUNNING (health: OK)
- systemd client: ACTIVE (connected: YES)

**Logs:**
```bash
./whisperflow logs
```
Output:
- Tails docker-compose logs (server)
- Tails journalctl logs (client)
- Ctrl+C to exit

**Shutdown:**
```bash
./whisperflow stop
```
Flow:
1. systemd stops client (graceful)
2. Docker Compose stops server (graceful)

### 4.3 Auto-Start on WSL2 Boot

**Docker Container:**
```yaml
restart: unless-stopped
```
- Docker daemon auto-starts on WSL2 boot
- Container auto-starts with daemon

**systemd Client:**
```bash
systemctl enable whisperflow-client
```
- Service enabled for multi-user.target
- Starts automatically after Docker

**Validation:**
```bash
# Simulate WSL2 restart
wsl.exe --shutdown
# Wait 10s
# Open new WSL2 terminal
./whisperflow status  # Should show RUNNING
```

---

## 5. TECHNICAL DECISIONS

### 5.1 Port Standardization: 8181

**Rationale:**
- start_dictado.sh already uses 8181
- Client hardcoded to ws://localhost:8181
- Avoids conflicts with other services on 8080

**Changes Required:**
- Dockerfile ENV PORT=8181
- Dockerfile CMD --port 8181
- Dockerfile EXPOSE 8181
- docker-compose.yml ports: "8181:8181"

### 5.2 Model Volume Mount: Read-Only

**Rationale:**
- Models are large (462MB)
- Models don't change frequently
- Faster Docker builds
- Disk space efficiency

**Implementation:**
```yaml
volumes:
  - ./whisperflow/models:/app/whisperflow/models:ro
```

**Risk Mitigation:**
- Validate models exist before Docker build
- Add check in install.sh: `ls whisperflow/models/*.pt`

### 5.3 systemd Over Supervisor/PM2

**Rationale:**
- Native to Ubuntu/WSL2
- Robust process management
- Auto-restart on failure
- Logging via journald (standard)
- No additional dependencies

**Alternatives Considered:**
- supervisord: Extra dependency
- pm2: Node.js ecosystem (not needed)
- Docker for client: Breaks hardware access

### 5.4 CLI Script in Bash (Not Python)

**Rationale:**
- Simple control flow
- No Python dependencies
- Familiar to sysadmins
- Easy to debug
- Works without .venv activation

**Features:**
- Dependency checks (docker, systemctl)
- Clear error messages
- Colored output (optional)
- Help message

---

## 6. MISSING PIECES IDENTIFIED

### 6.1 Client Reconnection Logic (CRITICAL)

**Current Code:**
```python
async def connect_to_server(self):
    try:
        self.websocket = await websockets.connect(self.server_url)
        self.is_connected = True
    except Exception as e:
        print(f"❌ Error: {e}")
        self.is_connected = False
```

**Problem:** One attempt, then gives up.

**Solution:**
```python
async def connect_to_server(self, max_retries=5):
    for attempt in range(max_retries):
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            print("✅ Connected to WhisperFlow")
            asyncio.create_task(self.listen_transcriptions())
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                print(f"⚠️ Retry {attempt+1}/{max_retries} in {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"❌ Failed after {max_retries} attempts")
                self.is_connected = False
```

**Implementation:** Modify universal_dictation_client.py

### 6.2 Health Check Endpoint

**Assumption:** Exists at `/health`

**Validation Needed:**
```bash
curl http://localhost:8181/health
```

**Expected Response:** HTTP 200 with JSON

**If Missing:** Must add to fast_server.py:
```python
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### 6.3 Docker Compose File (Does Not Exist)

**Status:** Missing (confirmed via file reads)

**Must Create:** docker-compose.yml in project root

### 6.4 systemd Service File (Does Not Exist)

**Status:** Missing

**Must Create:** whisperflow-client.service

### 6.5 CLI Control Script (Does Not Exist)

**Status:** Missing

**Must Create:** whisperflow bash script

### 6.6 Installation Script (Does Not Exist)

**Status:** Missing

**Must Create:** install.sh

### 6.7 .dockerignore (May Not Exist)

**Status:** Unknown (not read)

**Should Create:** To exclude .venv, .git, etc.

---

## 7. RISK ANALYSIS

### 7.1 High Risk

**Risk:** Docker not installed or user not in docker group
- **Impact:** Install fails
- **Mitigation:** install.sh checks `docker --version` and adds user to group
- **Fallback:** Clear error message with installation instructions

**Risk:** Whisper models missing
- **Impact:** Server container fails to start
- **Mitigation:** install.sh validates `ls whisperflow/models/*.pt`
- **Fallback:** Error message + download instructions

**Risk:** WSL2 audio not configured
- **Impact:** Client can't capture microphone
- **Mitigation:** Test audio in install.sh with `pactl info`
- **Fallback:** Error message + WSLg setup guide

### 7.2 Medium Risk

**Risk:** Port 8181 already in use
- **Impact:** Docker container fails to start
- **Mitigation:** Health check in install.sh: `lsof -i :8181`
- **Fallback:** Error message + instructions to kill process

**Risk:** systemd not available
- **Impact:** Client service can't be installed
- **Mitigation:** Check `systemctl --version` in install.sh
- **Fallback:** Manual client execution only

**Risk:** Client crashes in loop
- **Impact:** systemd restarts repeatedly (logs spam)
- **Mitigation:** `Restart=on-failure` with backoff
- **Configuration:** `RestartSec=10s`

### 7.3 Low Risk

**Risk:** Backward compatibility broken
- **Impact:** Users can't use manual workflow
- **Mitigation:** Don't modify existing scripts
- **Validation:** Test start_dictado.sh still works

**Risk:** Logs rotation not configured
- **Impact:** Disk fills with logs
- **Mitigation:** Docker Compose logging config + journald defaults
- **Monitoring:** User responsibility

---

## 8. SUCCESS METRICS

### 8.1 Installation Success

**Command:**
```bash
./install.sh
```

**Expected Output:**
```
🔧 Installing WhisperFlow Auto-Start System...
✅ Docker installed: 24.0.7
✅ User in docker group
✅ Whisper models found: 2 files
✅ systemd service installed
✅ systemd service enabled
✅ CLI tool installed: /usr/local/bin/whisperflow
✅ Docker image built
✅ Installation complete!
```

**Validation:**
- Docker Compose file exists
- systemd service file in /etc/systemd/system/
- CLI script in /usr/local/bin/
- Docker image tagged

### 8.2 Operational Success

**Command:**
```bash
./whisperflow start
```

**Expected Output:**
```
🚀 Starting WhisperFlow...
✅ Docker server started
⏳ Waiting for health check...
✅ Server healthy
✅ Client service started
✅ WhisperFlow ready! (Ctrl+Space to dictate)
```

**Validation:**
- `docker ps` shows whisperflow-server RUNNING
- `systemctl status whisperflow-client` shows ACTIVE
- `curl localhost:8181/health` returns 200
- Ctrl+Space triggers recording

**Command:**
```bash
./whisperflow status
```

**Expected Output:**
```
📊 WhisperFlow Status:

Docker Server:
NAME                  STATUS    HEALTH    PORTS
whisperflow-server    Up 2m     healthy   0.0.0.0:8181->8181/tcp

systemd Client:
● whisperflow-client.service - WhisperFlow Universal Dictation Client
   Loaded: loaded (/etc/systemd/system/whisperflow-client.service; enabled)
   Active: active (running) since [timestamp]
```

### 8.3 Resilience Validation

**Test 1: Server Crash Recovery**
```bash
docker kill whisperflow-server
# Wait 10s
./whisperflow status
# Expected: Server restarted, client reconnected
```

**Test 2: Client Crash Recovery**
```bash
sudo systemctl stop whisperflow-client
sudo systemctl start whisperflow-client
# Expected: Client reconnects to server
```

**Test 3: WSL2 Reboot Auto-Start**
```bash
wsl.exe --shutdown
# Open new WSL2 terminal
./whisperflow status
# Expected: Both running automatically
```

### 8.4 End-to-End Dictation Test

**Steps:**
1. Open any text editor (VS Code, Notepad, etc.)
2. Click in text field (focus)
3. Press Ctrl+Space
4. Speak: "This is a test of the dictation system"
5. Press Ctrl+Space again (stop)
6. Wait for transcription (~2-3s)

**Expected:**
- Text appears in text editor
- Console shows: "📝 Transcrito: This is a test of the dictation system"
- Text is properly formatted (capitalized, punctuation)

---

## 9. NEXT STEPS (Phase 1)

### 9.1 Task Hierarchy Generation

**Phase 1 Output:**
- L1 Milestones (7 major components)
- L2 Tasks (breakdown of each milestone)
- L3 Micro-tasks (atomic implementation steps)

**L1 Milestones Identified:**
1. Docker Server Setup
2. systemd Service Setup
3. CLI Control Script
4. Auto-Start Configuration
5. Logging & Monitoring
6. Error Handling & Resilience
7. Documentation

**Total Estimated Tasks:** ~35 L3 tasks

### 9.2 Implementation Order (Dependency-Based)

1. **Docker Foundation** (Iteration 1)
   - Modify Dockerfile
   - Create .dockerignore
   - Validate build

2. **Docker Compose** (Iteration 2)
   - Create docker-compose.yml
   - Test container startup
   - Validate health check

3. **systemd Service** (Iteration 3)
   - Create service file
   - Test manual start
   - Validate client connection

4. **CLI Control Script** (Iteration 4)
   - Implement all subcommands
   - Add dependency checks
   - Test workflows

5. **Auto-Start** (Iteration 5)
   - Configure restart policies
   - Create install.sh
   - Test installation

6. **Integration Testing** (Iteration 6)
   - End-to-end workflows
   - Resilience tests
   - Backward compatibility

7. **Resilience Enhancements** (Iteration 7)
   - Client reconnection
   - Timeout handling
   - Error recovery

8. **Logging & Monitoring** (Iteration 8)
   - Configure log rotation
   - Test log commands
   - Validate accessibility

---

## 10. TECHNICAL DEBT & LIMITATIONS

### 10.1 Known Limitations

**WSL2 Specific:**
- System is WSL2-specific (not portable to native Linux)
- Audio config hardcoded to WSLg paths
- Won't work on Windows native or macOS

**Deployment:**
- No cloud deployment (local only)
- No remote server support
- Client and server must be on same machine

**Security:**
- No authentication on WebSocket
- No HTTPS/WSS
- Localhost-only binding

**Scalability:**
- Single user only
- No multi-client support
- No load balancing

### 10.2 Future Enhancements (Out of Scope)

**Nice to Have:**
- Web UI for configuration
- Multiple hotkey profiles
- Cloud deployment option
- Remote server support
- Authentication layer
- Metrics dashboard

**Documentation:**
- Video tutorial
- Troubleshooting flowchart
- Performance tuning guide
- Model comparison guide

---

## 11. PHASE 0 COMPLETION SUMMARY

**Files Analyzed:**
- ✅ Dockerfile (45 lines)
- ✅ start_dictado.sh (61 lines)
- ✅ universal_dictation_client.py (226 lines)
- ✅ requirements.txt (18 dependencies)
- ✅ whisperflow/models/ (2 model files, 535MB total)

**Key Findings:**
- ✅ Port discrepancy identified (8080 vs 8181)
- ✅ Missing reconnection logic identified
- ✅ Missing Docker Compose file
- ✅ Missing systemd service
- ✅ Missing CLI control script
- ✅ Missing installation script
- ✅ WSL2 audio config documented
- ✅ Dependency graph created
- ✅ Risk analysis completed

**Technical Decisions Made:**
- ✅ Port 8181 standardization
- ✅ Model volume mount strategy (read-only)
- ✅ systemd for client (not Docker)
- ✅ Bash CLI script (not Python)
- ✅ Backward compatibility preserved

**Deliverables:**
- ✅ Analysis document (this file)
- ✅ Architecture diagrams (ASCII)
- ✅ Dependency graph
- ✅ Risk analysis matrix
- ✅ Success criteria defined

**Status:** Phase 0 COMPLETE (0% → 10%)

**Next Phase:** Phase 1 - Generate Task Hierarchy (L1/L2/L3)

---

**Agent:** ultrathink-engineer
**Project:** whisperflow-cloud
**Timestamp:** 2025-10-18 15:30:00
