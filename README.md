# Computer Use Agent

Full-stack Claude Computer Use style application with FastAPI, React, PostgreSQL, Docker Compose, nginx, WebSocket streaming, screenshot artifacts, and noVNC desktop execution.

## Documentation

- [Final Project Report](./docs/FINAL_REPORT.md)
- [API Reference](./docs/API_REFERENCE.md)
- [API Interface Parameters](./docs/API_PARAMETERS.md)
- [Architecture Overview](./docs/ARCHITECTURE_OVERVIEW.md)
- [Project Introduction Script](./docs/PROJECT_INTRO_SCRIPT.md)
- [WebSocket and Timeline Design](./docs/WEBSOCKET_TIMELINE.md)
- [Test Plan](./TEST_PLAN.md)
- [Security Notes](./SECURITY.md)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run Locally

Local development uses SQLite by default:

```text
DATABASE_URL=sqlite:///./dev.db
```

```bash
uvicorn app.main:app --reload
```

Run the React frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open local development URLs:

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- React app: http://127.0.0.1:5173

## Test

```bash
pytest
cd frontend && npm run build
```

## Docker Compose Deployment

The recommended local deployment path is:

```bash
./deploy.sh
```

The script builds and starts all services, then checks the API and web UI.

Useful commands:

```bash
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh down
```

You can also run Docker Compose directly:

```bash
docker compose up --build -d
```

Docker deployment URLs:

| Service | URL |
|---|---|
| Web UI through nginx | http://127.0.0.1/ |
| API health | http://127.0.0.1:8000/health |
| API docs | http://127.0.0.1:8000/docs |
| noVNC direct URL | http://127.0.0.1:6080/vnc.html |

## Persistence

The app creates database tables automatically at startup. Local SQLite data is stored in `dev.db`, which is ignored by Git. In Docker Compose, PostgreSQL data is stored in the `postgres_data` volume.

Main persisted data:

- users
- relay configs
- sessions
- messages
- events
- screenshot artifact metadata

## Agent Modes

The backend supports mode-based AgentRunner selection:

```text
AGENT_MODE=mock
AGENT_MODE=fake_anthropic
AGENT_MODE=anthropic
```

`mock` is implemented for local development and demos. `fake_anthropic` simulates the Anthropic Computer Use event shape without an API key. `anthropic` vendors the official `computer_use_demo` package and calls its `sampling_loop()` behind the same runner interface.

For Anthropic mode, configure:

```text
AGENT_MODE=anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_TOOL_VERSION=computer_use_20250124
```

Leave `ANTHROPIC_BASE_URL` empty for the official Anthropic API. Set it only for Anthropic-compatible proxy providers.

Anthropic mode requires the app process to run inside a desktop-capable container with X11, VNC, `xdotool`, screenshot tools, `WIDTH`, `HEIGHT`, and `DISPLAY_NUM`, matching the official demo environment. The provided Dockerfile starts FastAPI and noVNC in the same container for this reason.

The UI can also pass the current Relay API URL, API key, and selected model directly to `Run Task`. This lets users test and execute against different Anthropic-compatible providers without changing container environment variables.

Secrets should stay in `.env`, Docker/Kubernetes secrets, or a managed secret store. Do not commit real keys. See [SECURITY.md](./SECURITY.md) for secret and encryption guidance.

## API

```text
GET    /health
GET    /api/config
POST   /api/auth/register
POST   /api/auth/login
GET    /api/relay-config
POST   /api/relay-config/test-and-save
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/history
GET    /api/sessions/{session_id}
DELETE /api/sessions/{session_id}
POST   /api/sessions/{session_id}/cancel
POST   /api/sessions/{session_id}/messages
GET    /api/sessions/{session_id}/messages
GET    /api/sessions/{session_id}/events?run_id={task_run_id}
GET    /api/sessions/{session_id}/vnc
GET    /api/sessions/history/{run_id}
GET    /api/artifacts/sessions/{session_id}?run_id={task_run_id}
GET    /api/artifacts/{artifact_id}/file
WS     /ws/sessions/{session_id}
```

Full endpoint details are documented in [API_REFERENCE.md](./docs/API_REFERENCE.md).

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo"}'

curl -X POST http://127.0.0.1:8000/api/sessions/{session_id}/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"Open example.com"}'
```
