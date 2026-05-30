# WebSocket and Timeline Design

## Purpose

The WebSocket stream keeps the frontend synchronized with backend agent execution. `Run Task` returns after the backend accepts the task, and the WebSocket becomes the primary channel for progress, screenshots, completion, and errors.

The VNC window shows the actual desktop where Claude Computer Use operates. The execution steps panel shows the structured backend event stream.

## Connection

```text
WS /ws/sessions/{session_id}?token=<jwt>
```

Connection behavior:

1. The frontend creates a session with `POST /api/sessions`.
2. The frontend opens `WS /ws/sessions/{session_id}`.
3. The backend validates the JWT token query parameter.
4. The backend verifies that the session exists and belongs to the authenticated user.
5. If the session is valid, the backend accepts the WebSocket.
6. The backend sends an initial `connected` message.
7. Every new session event is broadcast to connected clients.

Initial message:

```json
{
  "type": "connected",
  "session_id": "...",
  "payload": {}
}
```

Event message shape:

```json
{
  "id": "...",
  "session_id": "...",
  "type": "tool_started",
  "payload": {},
  "created_at": "..."
}
```

## Event Source

The event stream is produced by the backend agent runner:

```text
POST /api/sessions/{session_id}/messages
  -> app.api.sessions.create_message()
  -> task_runs row created with status=running
  -> background asyncio task
  -> app.services.agent_runner.AnthropicAgentRunner.run()
  -> computer_use_demo.sampling_loop()
  -> event persistence
  -> WebSocket broadcast
```

Every event is both:

- persisted in PostgreSQL through the session manager
- broadcast to active WebSocket clients

This means the frontend can recover historical events using:

```text
GET /api/sessions/{session_id}/events
```

Run History is stored separately in `task_runs`; it is updated when the task finishes or fails.

## Timeline Event Types

| Type | Created When | Typical Payload |
|---|---|---|
| `user_message` | User submits `Run Task` | `message_id`, `content` |
| `agent_message` | Model emits text or backend status | `message_id`, `content`, `model`, `base_url` |
| `tool_started` | Model calls a Computer Use tool | `tool_use_id`, `tool`, `input` |
| `tool_result` | Tool execution finishes | `tool_use_id`, `output`, `error`, `has_image` |
| `screenshot` | Tool result contains an image | `tool_use_id`, `media_type`, `artifact_id`, `url` |
| `completed` | Agent run finishes | `mode`, `message_id` |
| `error` | API or tool execution fails | `message` |

## Expected Timeline

For a prompt like `Open terminal`, a normal timeline looks like this:

```text
Step 1: user_message
  User prompt is saved.

Step 2: agent_message
  Backend starts Claude Computer Use with the selected model.

Step 3: tool_started
  Claude requests a tool call, for example bash or computer.

Step 4: tool_result
  The tool returns output or an error.

Step 5: screenshot
  If a screenshot is available, it is stored as an artifact and shown by the frontend.

Step 6: agent_message
  Claude reports progress or final text.

Step 7: completed
  Session status becomes completed.
```

If execution fails, the timeline ends with `error` and the session status becomes `failed`.

If the user clicks `Cancel`, the backend cancels the task, cleans up desktop processes, and marks the session as failed with a cancellation message.

## Screenshot Handling

Screenshot flow:

```text
Computer Use tool result
  -> base64 image returned by tool
  -> screenshot event created with current run_id
  -> artifact service stores PNG on disk
  -> PostgreSQL stores artifact metadata with session_id and run_id
  -> WebSocket broadcasts screenshot event
  -> frontend reloads /api/artifacts/sessions/{session_id}?run_id={run_id}
  -> frontend loads image through /api/artifacts/{artifact_id}/file
```

The screenshot event payload is normalized before frontend display. Instead of relying only on a large `base64_image` field, the backend attaches artifact metadata such as:

```json
{
  "tool_use_id": "...",
  "run_id": "...",
  "media_type": "image/png",
  "artifact_id": "...",
  "url": "/api/artifacts/{artifact_id}/file"
}
```

## Frontend Display

The frontend uses two complementary views:

| View | Purpose |
|---|---|
| VNC window | Shows the real desktop where Claude operates |
| Execution Steps | Shows recent structured events from the active run |
| Screenshot Timeline | Shows recent persisted screenshots for the active run |
| Run History Detail | Replays one historical run using `run_id`-filtered events and artifacts |

Screenshot events can also render a matching thumbnail inside the execution steps panel. The VNC panel remains the primary place to watch live GUI actions.

## Failure Modes

Common failure cases:

| Failure | Behavior |
|---|---|
| Invalid or missing token | WebSocket closes with policy violation |
| Invalid session ID or wrong user | WebSocket closes with policy violation |
| Relay connection works but model lacks Computer Use | `Run Task` returns execution failure |
| Relay returns 401, 403, or 502 | Backend classifies the error as authentication, model compatibility, or upstream failure |
| Task timeout | Execution control stops the run and marks the session failed with a timeout message |
| User cancellation | Cancel endpoint cancels the current task |

## Design Notes

- The WebSocket is session-scoped, so clients only receive events for the active session.
- Events are persisted before or during broadcast, so reconnecting clients can reload state from HTTP.
- VNC desktop execution is visible because the agent prompt instructs GUI commands to use `DISPLAY=:1`.
- Current implementation resets a shared desktop for new sessions. It does not yet create a separate desktop container per session.
