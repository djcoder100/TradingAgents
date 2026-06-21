# Distributed Deployment Guide

This guide covers deploying TradingAgents in a **cloud-ready, distributed architecture** where the engine, state service, and web frontend run as separate processes (or on different machines).

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Competition State Service (FastAPI)             │
│ - Central state store                           │
│ - Persists to disk (~/.tradingagents/)         │
│ - Port: 9000                                    │
└─────────────────────────────────────────────────┘
         ▲                          ▲
      POST updates              GET state
         │                          │
    ┌────┴────────┐        ┌──────┴─────────┐
    │ Engine      │        │ Web API        │
    │ Process     │        │ + Frontend     │
    │ (separate)  │        │ (separate)     │
    └─────────────┘        └────────────────┘
```

**Benefits:**
- ✅ Engine can restart independently without losing state
- ✅ Web dashboard remains live while engine is down
- ✅ Scales to cloud (Kubernetes, Docker Compose, serverless)
- ✅ Multiple engines can write to one state service
- ✅ Multiple dashboards can read from one state service

## Local Testing (All on localhost)

### Terminal 1 — Start everything with one command:

```bash
./scripts/competition-start-distributed.sh
```

This starts:
1. State Service (port 9000)
2. Engine (separate process)
3. Web API (port 8000)
4. Frontend dev server (port 5173)

Opens http://localhost:5173/competition automatically.

### Or start individually:

**Terminal 1 — State Service:**
```bash
uv run uvicorn competition.state_service:app --host 0.0.0.0 --port 9000
```

**Terminal 2 — Engine:**
```bash
export COMPETITION_STATE_SERVICE_URL=http://localhost:9000
uv run competition --mock --dry-run --instruments XAUUSD
```

**Terminal 3 — Web + Frontend:**
```bash
export COMPETITION_STATE_SERVICE_URL=http://localhost:9000
./scripts/competition-start-distributed.sh --web-only
```

## Cloud Deployment (AWS/GCP/Azure/Heroku)

### Option 1: Docker Compose (Recommended for testing)

```yaml
version: '3.8'
services:
  state-service:
    build:
      context: .
      dockerfile: Dockerfile.state-service
    ports:
      - "9000:9000"
    volumes:
      - state-volume:/root/.tradingagents

  engine:
    build:
      context: .
      dockerfile: Dockerfile.engine
    environment:
      COMPETITION_STATE_SERVICE_URL: "http://state-service:9000"
      COMPETITION_INSTRUMENTS: "EURUSD,GBPUSD,XAUUSD"
      COMPETITION_DRY_RUN: "1"
      # LLM config
      TRADINGAGENTS_LLM_PROVIDER: "deepseek"
      TRADINGAGENTS_LLM_BACKEND_URL: "https://gateway-eu.pydantic.dev/proxy/doubleword"
      DEEPSEEK_API_KEY: "${DEEPSEEK_API_KEY}"
    depends_on:
      - state-service

  web-api:
    build:
      context: .
      dockerfile: Dockerfile.web
    ports:
      - "8000:8000"
    environment:
      COMPETITION_STATE_SERVICE_URL: "http://state-service:9000"
    depends_on:
      - state-service

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"

volumes:
  state-volume:
```

### Option 2: Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: competition-state-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: state-service
  template:
    metadata:
      labels:
        app: state-service
    spec:
      containers:
      - name: state-service
        image: competition:state-service
        ports:
        - containerPort: 9000
        volumeMounts:
        - name: state-volume
          mountPath: /root/.tradingagents
  volumes:
  - name: state-volume
    emptyDir: {}

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: competition-engine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: engine
  template:
    metadata:
      labels:
        app: engine
    spec:
      containers:
      - name: engine
        image: competition:engine
        env:
        - name: COMPETITION_STATE_SERVICE_URL
          value: "http://competition-state-service:9000"
        - name: COMPETITION_INSTRUMENTS
          value: "EURUSD,GBPUSD,XAUUSD"
        - name: TRADINGAGENTS_LLM_PROVIDER
          value: "deepseek"
        - name: DEEPSEEK_API_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: deepseek-key
```

### Option 3: Heroku (Procfile)

```procfile
state-service: uv run uvicorn competition.state_service:app --host 0.0.0.0 --port $PORT
engine: uv run competition --mock --dry-run --instruments EURUSD,GBPUSD,XAUUSD
web: uv run competition --web-only
```

Set environment variables:
```bash
heroku config:set COMPETITION_STATE_SERVICE_URL=https://my-app-state-service.herokuapp.com
heroku config:set TRADINGAGENTS_LLM_PROVIDER=deepseek
heroku config:set DEEPSEEK_API_KEY=...
```

## Configuration

### Environment Variables

```bash
# State service
COMPETITION_STATE_SERVICE_URL=http://localhost:9000  # Engine and web read this
COMPETITION_STATE_SERVICE_PORT=9000                   # Port for state service

# Engine
COMPETITION_INSTRUMENTS=EURUSD,GBPUSD,XAUUSD
COMPETITION_DRY_RUN=1                                  # 0 for live trading
COMPETITION_NO_LLM=1                                   # 1 to skip LLM
COMPETITION_ANALYSTS=market,social,news,fundamentals

# LLM
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_LLM_BACKEND_URL=https://gateway-eu.pydantic.dev/proxy/doubleword
DEEPSEEK_API_KEY=...

# Web
TRADINGAGENTS_WEB_PORT=8000
VITE_PORT=5173
LOG_DIR=.logs
```

## How It Works

### Engine writes to State Service:

1. Engine creates `StateServiceClient`
2. On each update (analysis progress, trade, etc.):
   - **In-process**: Updates local state bus + persists to disk
   - **Network**: POSTs update to state service
3. State service receives update → updates in-memory state → persists to disk

### Web reads from State Service:

1. Web API boots, tries to get bus from app.state
2. If no bus (separate process mode), web reads from state service
3. Frontend polls web API every 2 seconds
4. Web API returns state from either bus or state service (transparent to frontend)

### Both survive independently:

- Engine down? Web still serves historical data from state service
- Web down? Engine keeps running and publishing to state service
- State service down? Engine and web fall back to local persistence
- Restart any component without losing state

## Monitoring & Logs

```bash
# Watch all logs
tail -f .logs/*.log

# Watch just the state service
tail -f .logs/competition-state-service.log

# Watch the engine
tail -f .logs/competition-engine.log

# Check state service health
curl http://localhost:9000/api/health

# Get current state
curl http://localhost:9000/api/competition/state | jq .
```

## Performance Notes

- **State service**: < 50ms per request (in-process dict + disk sync)
- **Engine → State service**: HTTP POST with 2s timeout (non-blocking)
- **Web → State service**: HTTP GET with 2s timeout, polled every 500ms
- **Persistence**: Disk writes are async, so no blocking I/O

For high-frequency requirements, consider adding Redis/RabbitMQ instead of HTTP polling. The state service makes that a drop-in replacement.

## Troubleshooting

**State service won't start:**
```bash
# Port already in use?
lsof -ti:9000 | xargs kill -9

# Try a different port
uv run uvicorn competition.state_service:app --port 9001
export COMPETITION_STATE_SERVICE_URL=http://localhost:9001
```

**Engine can't connect to state service:**
```bash
# Check state service is running
curl http://localhost:9000/api/health

# Check COMPETITION_STATE_SERVICE_URL is set correctly
echo $COMPETITION_STATE_SERVICE_URL

# Check firewall isn't blocking
nc -zv localhost 9000
```

**Web sees old data:**
```bash
# State service persists to ~/.tradingagents/shared_state.json
# Clear it to reset
rm ~/.tradingagents/shared_state.json

# Restart web
./scripts/competition-start-distributed.sh --web-only
```

## Next: Create Dockerfiles

To deploy on cloud platforms, you'll need:
- `Dockerfile.state-service` — runs state service
- `Dockerfile.engine` — runs competition engine
- `Dockerfile.web` — runs web API
- `frontend/Dockerfile` — builds React app

Each should be minimal and use multi-stage builds for small image sizes.
