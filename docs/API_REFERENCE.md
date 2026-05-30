# API Reference

Base URL for local Docker deployment:

```text
http://127.0.0.1:8000
```

Most business endpoints require JWT authentication:

```text
Authorization: Bearer <token>
```

The token is returned by `POST /api/auth/register` and `POST /api/auth/login`. User-scoped APIs derive `user_id` from the JWT `sub` claim; clients should not send `user_id` as the source of truth.

## Health and Config

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Check whether the API service is running |
| `GET` | `/api/config` | Return public frontend config such as environment, agent mode, model setting, and VNC URL |

## Authentication

### Register

```text
POST /api/auth/register
```

Creates a new user.

Request body:

```json
{
  "username": "demo",
  "email": "demo@example.com",
  "password": "password"
}
```

Response:

```json
{
  "token": "...",
  "user": {
    "id": "...",
    "username": "demo",
    "email": "demo@example.com",
    "created_at": "..."
  }
}
```

### Login

```text
POST /api/auth/login
```

Authenticates an existing user.

Request body:

```json
{
  "username": "demo",
  "password": "password"
}
```

## Relay Config

### List Relay Configs

```text
GET /api/relay-config
```

Returns saved Relay configurations for the authenticated user.

### Test and Save Relay Config

```text
POST /api/relay-config/test-and-save
```

Tests a Relay API URL and key, loads available models, and saves the configuration if the connection succeeds.

The API key is encrypted before persistence. The response returns the decrypted key only to the authenticated owner so the frontend can refill the form.

Request body:

```json
{
  "api_url": "https://example-relay.com",
  "api_key": "...",
  "model": "claude-sonnet-4-5"
}
```

Notes:

- This endpoint checks connection and model listing.
- It does not guarantee that the selected model supports Claude Computer Use.
- Computer Use compatibility is validated during `Run Task`.

## Sessions and Tasks

### Create Session

```text
POST /api/sessions
```

Creates a new session and resets the shared VNC desktop.

Request body:

```json
{
  "name": "Demo Session",
}
```

### List Sessions

```text
GET /api/sessions
```

Lists sessions for the authenticated user.

### Run History

```text
GET /api/sessions/history
```

Returns data for the authenticated user's Run History table, including prompt, time, response time, result, model, base URL, and error.

Each row represents one `Run Task` execution from the `task_runs` table. Multiple runs in the same session are returned as separate rows.

### Run History Detail

```text
GET /api/sessions/history/{run_id}
```

Returns one run plus its persisted events and screenshot artifacts. The frontend uses this endpoint to review a previous `Run Task` execution without mixing timeline items or screenshots from other runs in the same session.

### Get Session

```text
GET /api/sessions/{session_id}
```

Returns one session and its current status.

### Terminate Session

```text
DELETE /api/sessions/{session_id}
```

Terminates a session.

### Cancel Running Task

```text
POST /api/sessions/{session_id}/cancel
```

Cancels the currently running task for the session.

Possible errors:

| Status | Meaning |
|---|---|
| `404` | Session does not exist |
| `409` | Session is not running |

### Run Task

```text
POST /api/sessions/{session_id}/messages
```

Submits a prompt and starts Claude Computer Use execution.

Request body:

```json
{
  "content": "Open terminal",
  "relay_config_id": "...",
  "relay_api_url": "https://example-relay.com",
  "relay_api_key": "...",
  "model": "claude-sonnet-4-5"
}
```

Execution behavior:

- The prompt is saved as a user message.
- The session status changes to `running`.
- The HTTP response returns immediately after the task is accepted.
- The selected Relay URL, API key, and model are passed into the agent runner.
- The agent runs in a backend task and uses Claude Computer Use tools to operate the VNC desktop.
- Events are stored and broadcast over WebSocket.
- The frontend should treat WebSocket events and session status as the source of truth for progress and completion.
- The session becomes `completed` or `failed` after the backend task exits.

Possible errors:

| Status | Meaning |
|---|---|
| `404` | Session does not exist |
| `409` | Session is terminated or already running |
| `499` | Task was cancelled |
| `500` | Agent execution failed |

### List Messages

```text
GET /api/sessions/{session_id}/messages
```

Returns user and assistant messages for a session.

### List Events

```text
GET /api/sessions/{session_id}/events?run_id={task_run_id}
```

Returns persisted execution events for a session. When `run_id` is provided, only events from that `Run Task` execution are returned.

### Get VNC Connection

```text
GET /api/sessions/{session_id}/vnc
```

Returns VNC connection information for the session and ensures the desktop log window is available.

## Artifacts

### List Session Artifacts

```text
GET /api/artifacts/sessions/{session_id}?run_id={task_run_id}
```

Returns screenshot and artifact metadata for a session. When `run_id` is provided, the response is limited to artifacts produced by that single `Run Task` execution. The frontend uses this filtered response so the screenshot timeline does not mix images from multiple runs in the same session.

`run_id` is optional for compatibility. Without it, the endpoint returns all artifacts for the session.

### Get Artifact File

```text
GET /api/artifacts/{artifact_id}/file
```

Returns the stored artifact file, such as a screenshot PNG.

## WebSocket

```text
WS /ws/sessions/{session_id}
```

Streams session execution events in real time. Browser clients pass the JWT as a `token` query parameter:

```text
WS /ws/sessions/{session_id}?token=<token>
```

See [WEBSOCKET_TIMELINE.md](./WEBSOCKET_TIMELINE.md).

## Endpoint Count

| Type | Count |
|---|---:|
| HTTP endpoints | 18 |
| WebSocket endpoints | 1 |
| Total | 19 |
