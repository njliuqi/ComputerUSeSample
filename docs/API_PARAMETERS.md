# API Interface Parameters

本文件用于说明当前后端接口需要传什么参数，适合前端联调、Postman 测试和作业展示使用。

## Base URL

本地 Docker 环境：

```text
http://127.0.0.1:8000
```

前端访问入口：

```text
http://127.0.0.1/
```

## Authentication

除 `/health`、`/api/config`、`/api/auth/register`、`/api/auth/login` 之外，业务接口都需要 JWT。

请求头：

```text
Authorization: Bearer <token>
Content-Type: application/json
```

`token` 由注册或登录接口返回。后端会从 token 中解析当前用户，前端不应该把 `user_id` 当作可信参数传给后端。

## Endpoint Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | No | API health check |
| `GET` | `/api/config` | No | Public runtime config |
| `POST` | `/api/auth/register` | No | Register user |
| `POST` | `/api/auth/login` | No | Login user |
| `GET` | `/api/relay-config` | Yes | List saved Relay configs |
| `POST` | `/api/relay-config/test-and-save` | Yes | Test Relay and save config |
| `POST` | `/api/sessions` | Yes | Create session and reset VNC desktop |
| `GET` | `/api/sessions` | Yes | List sessions |
| `GET` | `/api/sessions/history` | Yes | List Run History |
| `GET` | `/api/sessions/history/{run_id}` | Yes | Get one run detail |
| `GET` | `/api/sessions/{session_id}` | Yes | Get session |
| `DELETE` | `/api/sessions/{session_id}` | Yes | Terminate session |
| `POST` | `/api/sessions/{session_id}/cancel` | Yes | Cancel running task |
| `POST` | `/api/sessions/{session_id}/messages` | Yes | Run Task |
| `GET` | `/api/sessions/{session_id}/messages` | Yes | List messages |
| `GET` | `/api/sessions/{session_id}/events` | Yes | List execution events |
| `GET` | `/api/sessions/{session_id}/vnc` | Yes | Get VNC connection |
| `GET` | `/api/artifacts/sessions/{session_id}` | Yes | List screenshot artifacts |
| `GET` | `/api/artifacts/{artifact_id}/file` | Yes | Get artifact file |
| `WS` | `/ws/sessions/{session_id}` | Yes | Realtime execution stream |

## Health and Config

### GET `/health`

参数：无。

返回示例：

```json
{
  "status": "ok",
  "environment": "docker"
}
```

### GET `/api/config`

参数：无。

返回字段：

| Field | Type | Description |
|---|---|---|
| `environment` | string | Runtime environment |
| `agent_mode` | string | Agent mode, for example `anthropic` |
| `anthropic_model` | string | Default model from environment |
| `anthropic_base_url_configured` | boolean | Whether base URL is configured |
| `vnc_base_url` | string | VNC base URL |

## Authentication APIs

### POST `/api/auth/register`

注册用户。

Body:

| Field | Type | Required | Rule | Description |
|---|---|---:|---|---|
| `username` | string | Yes | 3-80 chars | Login username |
| `email` | string/null | No | max 255 chars | User email |
| `password` | string | Yes | 6-128 chars | Login password |

Example:

```json
{
  "username": "demo",
  "email": "demo@example.com",
  "password": "password123"
}
```

Response:

```json
{
  "token": "<jwt-token>",
  "user": {
    "id": "user-id",
    "username": "demo",
    "email": "demo@example.com",
    "created_at": "2026-05-30T00:00:00Z"
  }
}
```

### POST `/api/auth/login`

登录用户。

Body:

| Field | Type | Required | Rule | Description |
|---|---|---:|---|---|
| `username` | string | Yes | 3-80 chars | Login username |
| `password` | string | Yes | 6-128 chars | Login password |

Example:

```json
{
  "username": "demo",
  "password": "password123"
}
```

Response: same as register.

## Relay Config APIs

### GET `/api/relay-config`

获取当前登录用户保存过的 Relay 配置。

参数：无。

Response:

```json
{
  "user_id": "user-id",
  "configs": [
    {
      "id": "config-id",
      "user_id": "user-id",
      "api_url": "https://example-relay.com",
      "api_key": "decrypted-api-key-for-owner",
      "model": "claude-sonnet-4-5",
      "models": ["claude-sonnet-4-5"],
      "connection_status": "success",
      "last_tested_at": "2026-05-30T00:00:00Z"
    }
  ]
}
```

### POST `/api/relay-config/test-and-save`

测试 Relay API URL 和 API Key，获取模型列表，并保存配置。

Body:

| Field | Type | Required | Rule | Description |
|---|---|---:|---|---|
| `api_url` | string | Yes | 1-2048 chars | Relay API base URL |
| `api_key` | string | Yes | 1-4096 chars | Relay API key |
| `model` | string | No | max 120 chars | Selected/default model |
| `user_id` | string/null | No | max 36 chars | Legacy field, ignored as source of truth |

Example:

```json
{
  "api_url": "https://example-relay.com",
  "api_key": "sk-...",
  "model": "claude-sonnet-4-5"
}
```

Notes:

- `Test` 只验证 Relay URL、API Key 和模型列表。
- 是否支持 Claude Computer Use 会在 `Run Task` 时验证。
- API Key 会加密存储到数据库。

## Session and Task APIs

### POST `/api/sessions`

创建新 session，并 reset 共享 VNC 桌面。

Body:

| Field | Type | Required | Rule | Description |
|---|---|---:|---|---|
| `name` | string/null | No | max 120 chars | Session name |
| `user_id` | string/null | No | max 36 chars | Legacy field, ignored as source of truth |

Example:

```json
{
  "name": "demo-session"
}
```

Response:

```json
{
  "id": "session-id",
  "user_id": "user-id",
  "status": "created",
  "name": "demo-session",
  "created_at": "2026-05-30T00:00:00Z",
  "updated_at": "2026-05-30T00:00:00Z",
  "error": null
}
```

### GET `/api/sessions`

获取当前用户的 session 列表。

参数：无。

### GET `/api/sessions/{session_id}`

获取一个 session 的状态。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

### DELETE `/api/sessions/{session_id}`

终止一个 session。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

### POST `/api/sessions/{session_id}/cancel`

取消当前 session 中正在执行的任务。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Body: none.

Common errors:

| Status | Meaning |
|---|---|
| `404` | Session not found |
| `409` | Session is not running |

### POST `/api/sessions/{session_id}/messages`

执行一次 `Run Task`。这是前端 `Run Task` 按钮调用的核心接口。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Body:

| Field | Type | Required | Rule | Description |
|---|---|---:|---|---|
| `content` | string | Yes | 1-8000 chars | Task prompt |
| `relay_config_id` | string/null | No | max 36 chars | Saved Relay config ID |
| `relay_api_url` | string/null | No | max 2048 chars | Current Relay API URL from input box |
| `relay_api_key` | string/null | No | max 4096 chars | Current Relay API key from input box |
| `model` | string/null | No | max 120 chars | Selected model |
| `user_id` | string/null | No | max 36 chars | Legacy field, ignored as source of truth |

Example:

```json
{
  "content": "open firefox and access baidu.com",
  "relay_config_id": "config-id",
  "relay_api_url": "https://example-relay.com",
  "relay_api_key": "sk-...",
  "model": "claude-sonnet-4-5"
}
```

Response:

```json
{
  "id": "message-id",
  "session_id": "session-id",
  "role": "user",
  "content": "open firefox and access baidu.com",
  "created_at": "2026-05-30T00:00:00Z"
}
```

Important behavior:

- HTTP response only means the backend accepted the task.
- Real progress is sent through WebSocket.
- Backend creates a `task_run` row for this request.
- All events and screenshots are linked to the run by `run_id`.
- If the selected model does not support Claude Computer Use, the task fails with a classified error.

### GET `/api/sessions/{session_id}/messages`

获取 session 中的 user/assistant messages。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

### GET `/api/sessions/{session_id}/events`

获取执行事件。可以通过 `run_id` 只看某一次 Run Task。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Query parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `run_id` | string | No | Filter events by one task run |

Example:

```text
GET /api/sessions/session-id/events?run_id=run-id
```

Event response item:

| Field | Type | Description |
|---|---|---|
| `id` | string | Event ID |
| `session_id` | string | Session ID |
| `run_id` | string/null | Task run ID |
| `type` | string | `user_message`, `agent_message`, `tool_started`, `tool_result`, `screenshot`, `completed`, `error` |
| `payload` | object | Event detail |
| `created_at` | string | Event time |

### GET `/api/sessions/{session_id}/vnc`

获取 VNC 连接信息，并确保 VNC 中的执行日志窗口可用。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Response:

```json
{
  "session_id": "session-id",
  "status": "ready",
  "url": "http://localhost:6080/vnc.html?...",
  "view_only_url": "http://localhost:6080/vnc.html?...&view_only=true"
}
```

## Run History APIs

### GET `/api/sessions/history`

获取当前用户所有 Run Task 的历史记录。

参数：无。

Response item:

| Field | Type | Description |
|---|---|---|
| `id` | string | Run ID |
| `session_id` | string | Session ID |
| `user_id` | string/null | User ID |
| `message_id` | string/null | User message ID |
| `prompt` | string | Task prompt |
| `started_at` | string | Start time |
| `completed_at` | string/null | Completion time |
| `response_time_ms` | integer/null | Execution duration |
| `result` | string | `running`, `success`, or `failed` |
| `model` | string | Selected model |
| `base_url` | string | Relay API URL |
| `error` | string | Classified error message |

### GET `/api/sessions/history/{run_id}`

获取某一次 Run Task 的详情，包括 run 信息、events 和 screenshots。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `run_id` | string | Yes | Task run ID |

Response:

```json
{
  "run": {
    "id": "run-id",
    "session_id": "session-id",
    "prompt": "open firefox",
    "result": "success",
    "model": "claude-sonnet-4-5",
    "base_url": "https://example-relay.com",
    "error": ""
  },
  "events": [],
  "artifacts": []
}
```

## Artifact APIs

### GET `/api/artifacts/sessions/{session_id}`

获取某个 session 下的 artifact 元数据。通常用于截图列表。可以通过 `run_id` 只看某一次 Run Task 的截图。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Query parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `run_id` | string | No | Filter artifacts by one task run |

Example:

```text
GET /api/artifacts/sessions/session-id?run_id=run-id
```

Artifact response item:

| Field | Type | Description |
|---|---|---|
| `id` | string | Artifact ID |
| `session_id` | string | Session ID |
| `run_id` | string/null | Task run ID |
| `event_id` | string/null | Related screenshot event ID |
| `kind` | string | Usually `screenshot` |
| `media_type` | string | Usually `image/png` |
| `url` | string | File URL |
| `tool_use_id` | string/null | Related Computer Use tool call ID |
| `created_at` | string | Creation time |

### GET `/api/artifacts/{artifact_id}/file`

获取截图文件。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `artifact_id` | string | Yes | Artifact ID |

Query parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `token` | string | No | JWT token for browser image loading |

Auth options:

- Normal API call: use `Authorization: Bearer <token>`.
- Browser `<img>` loading: use `?token=<jwt-token>`.

Example:

```text
GET /api/artifacts/artifact-id/file?token=<jwt-token>
```

## WebSocket API

### WS `/ws/sessions/{session_id}?token=<jwt-token>`

实时接收当前 session 的执行事件。

Path parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | Yes | Session ID |

Query parameters:

| Field | Type | Required | Description |
|---|---|---:|---|
| `token` | string | Yes | JWT token |

Message example:

```json
{
  "id": "event-id",
  "session_id": "session-id",
  "run_id": "run-id",
  "type": "tool_started",
  "payload": {
    "tool_use_id": "tool-id",
    "tool": "computer",
    "input": {
      "action": "screenshot"
    }
  },
  "created_at": "2026-05-30T00:00:00Z"
}
```

## Common Status Codes

| Status | Meaning |
|---|---|
| `200` | Success |
| `201` | Created |
| `401` | Missing or invalid token |
| `404` | Resource not found or not owned by current user |
| `409` | Session state conflict, for example already running |
| `422` | Request validation failed |
| `500` | Backend execution error |

## Recommended Frontend Call Order

```text
1. POST /api/auth/login
2. GET  /api/relay-config
3. POST /api/relay-config/test-and-save
4. POST /api/sessions
5. GET  /api/sessions/{session_id}/vnc
6. WS   /ws/sessions/{session_id}?token=<jwt-token>
7. POST /api/sessions/{session_id}/messages
8. GET  /api/sessions/history
9. GET  /api/sessions/history/{run_id}
```
