# Final Project Report

## Project Summary

This project implements a Claude Computer Use style web application. Users can register, log in, configure an Anthropic-compatible Relay API, submit a task prompt, and watch the task execute inside a VNC desktop.

The application is built as a Docker Compose system:

- `nginx`: public web entry on `http://127.0.0.1/`
- `frontend`: React/Vite UI served on internal port `5173`
- `api`: FastAPI backend, agent runner, noVNC, and desktop process
- `db`: PostgreSQL database

The main user workflow is:

1. Register or log in.
2. Enter Relay API URL, API key, and select a model.
3. Test the Relay connection and save a successful configuration.
4. Create or use the current session.
5. Submit a prompt with `Run Task`.
6. The backend accepts the task immediately and continues execution in the background.
7. Watch progress through WebSocket events, the VNC window, and the execution step panel.
8. Review run history, events, screenshot timeline, and final status.

## Architecture

```text
Browser
  |
  | HTTP http://127.0.0.1/
  v
Nginx :80
  |
  | reverse proxy
  v
React Frontend :5173
  |
  | REST API + WebSocket
  v
FastAPI Backend :8000
  |
  | SQLAlchemy
  v
PostgreSQL :5432

FastAPI Backend
  |
  | Claude Computer Use tools
  v
Ubuntu desktop on DISPLAY=:1
  |
  | noVNC
  v
Browser VNC panel :6080
```

## Backend Design

The backend follows a layered FastAPI structure:

- `app/api`: HTTP and WebSocket route definitions.
- `app/services`: business logic for sessions, relay configs, artifacts, VNC, execution control, cancellation, and WebSocket broadcasting.
- `app/schemas`: Pydantic request and response models.
- `app/db`: SQLAlchemy database models and session setup.
- `computer_use_demo`: adapted Claude Computer Use runtime and tools.

Key backend capabilities:

- User registration and login.
- JWT authentication and backend-side current user resolution.
- PostgreSQL persistence for users, relay configs, sessions, messages, events, and artifacts.
- Session lifecycle management: `created`, `running`, `completed`, `failed`, `terminated`.
- Task cancellation.
- Execution timeout control.
- Background task execution for `Run Task`.
- Relay API connection testing.
- Claude Computer Use task execution with user-provided Relay URL, API key, and selected model.
- Event persistence and WebSocket streaming.
- Screenshot artifact persistence.
- Screenshot timeline display by session.
- VNC connection management and visible desktop execution.

## Data Model

Main database tables:

| Table | Purpose |
|---|---|
| `users` | Registered users and password hashes |
| `relay_configs` | User Relay API URL, API key, selected model, available models, connection status |
| `sessions` | Task sessions and execution status |
| `task_runs` | One row per Run Task execution, used by Run History |
| `messages` | User and assistant messages |
| `events` | Execution events used by timeline and WebSocket streaming, scoped by `run_id` when available |
| `artifacts` | Screenshot metadata and file references, scoped by `run_id` when available |

Screenshots are stored as files under the artifact storage directory. PostgreSQL stores metadata such as session ID, run ID, event ID, media type, file path, and tool use ID.

## Real-Time Streaming

Real-time updates use WebSocket:

```text
WS /ws/sessions/{session_id}
```

When the agent runs, the backend records events and broadcasts them to connected frontend clients. The frontend uses these events to update the execution steps panel and VNC-related task state.

Event types:

| Event Type | Meaning |
|---|---|
| `user_message` | User submitted a task prompt |
| `agent_message` | Model text or status message |
| `tool_started` | Claude requested a tool call |
| `tool_result` | Tool returned output or error |
| `screenshot` | Tool result contains a screenshot |
| `completed` | Task finished successfully |
| `error` | API, tool, or runtime error |

More detail is available in [WEBSOCKET_TIMELINE.md](./WEBSOCKET_TIMELINE.md).

## API Summary

The backend exposes:

- 18 HTTP endpoints.
- 1 WebSocket endpoint.

Main endpoint groups:

- Health and public config.
- Authentication.
- Relay config testing and persistence.
- Session and task execution.
- Message and event history.
- VNC connection info.
- Screenshot artifacts.

Full API reference is available in [API_REFERENCE.md](./API_REFERENCE.md).

Run History is backed by the `task_runs` table rather than being reconstructed from events. This keeps multiple `Run Task` executions in the same session separate, with their own prompt, model, base URL, result, error, start time, completion time, and response time.

## Deployment

The project can be deployed locally with:

```bash
./deploy.sh
```

The script builds and starts all Docker Compose services, then checks the backend and web UI.

Useful commands:

```bash
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh down
```

Default local URLs:

| Service | URL |
|---|---|
| Web UI | `http://127.0.0.1/` |
| API health | `http://127.0.0.1:8000/health` |
| API docs | `http://127.0.0.1:8000/docs` |
| noVNC | `http://127.0.0.1:6080/vnc.html` |

## Testing

Recommended validation commands:

```bash
pytest
cd frontend
npm run build
```

Docker validation:

```bash
./deploy.sh
./deploy.sh status
```

Manual end-to-end validation:

1. Open `http://127.0.0.1/`.
2. Register a new user.
3. Enter a Relay API URL and API key.
4. Click `Test`.
5. Select a model.
6. Enter a prompt such as `Open terminal`.
7. Click `Run Task`.
8. Confirm the execution appears in the VNC window and execution steps.
9. Confirm Run History records the prompt, response time, and result.

## Known Limitations

- The current VNC desktop is reset for a new session, but it is still a shared desktop process, not a fully isolated per-session desktop container.
- The Relay connection test verifies URL, API key, and model list. Actual `Run Task` execution also requires the selected model and provider to support Claude Computer Use beta tools.
- If a Relay provider rejects Computer Use requests, the backend returns a clear execution error even if the connection test succeeds.
- Relay API keys are encrypted before being persisted in PostgreSQL.
- The default JWT secret is development-only. Production deployment must set `JWT_SECRET_KEY`.
- The default API key encryption secret is development-only. Production deployment must set `API_KEY_ENCRYPTION_SECRET`.

## Scoring Alignment

| Rubric Area | Current Coverage |
|---|---|
| Backend design | FastAPI service layers, PostgreSQL persistence, session lifecycle, cancellation, timeout control, artifacts, VNC integration |
| Real-time streaming | WebSocket event stream, execution timeline events, screenshot artifact events |
| Code quality | Modular route/service/schema/db structure, targeted services for execution control and cancellation |
| Documentation | Final report, API reference, WebSocket/timeline documentation, deploy script |
