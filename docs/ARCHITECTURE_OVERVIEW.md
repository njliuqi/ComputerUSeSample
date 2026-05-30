# Architecture Overview

## System Architecture

```text
                         ┌────────────────────────┐
                         │        Browser          │
                         │  React Frontend UI      │
                         │  http://127.0.0.1/      │
                         └───────────┬────────────┘
                                     │
                                     │ HTTP
                                     ▼
                         ┌────────────────────────┐
                         │         nginx           │
                         │ Listen: 80              │
                         │ Proxy -> frontend:5173  │
                         └───────────┬────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────┐
│                         Docker Compose                         │
│                                                                │
│  ┌──────────────────────┐        HTTP / WS        ┌──────────┐ │
│  │ React Frontend        │ ─────────────────────▶ │ FastAPI  │ │
│  │ Vite / Port 5173      │                         │ Backend  │ │
│  └──────────────────────┘                         │ Port 8000│ │
│                                                   └────┬─────┘ │
│                                                        │       │
│                                                        │ SQL   │
│                                                        ▼       │
│                                                   ┌──────────┐ │
│                                                   │PostgreSQL│ │
│                                                   │ users    │ │
│                                                   │ sessions │ │
│                                                   │ task_runs│ │
│                                                   │ events   │ │
│                                                   │ artifacts│ │
│                                                   └──────────┘ │
│                                                                │
│  ┌──────────────────────┐                         ┌──────────┐ │
│  │ noVNC / VNC Desktop   │ ◀────────────────────── │ Agent    │ │
│  │ Port 6080 / 5900      │   Claude Computer Use   │ Runner   │ │
│  │ Ubuntu GUI DISPLAY=:1 │                         └──────────┘ │
│  └──────────────────────┘                              │        │
│                                                        │        │
│                                                        ▼        │
│                                             ┌──────────────────┐│
│                                             │ Relay API         ││
│                                             │ Base URL + Key    ││
│                                             │ Selected Model    ││
│                                             └──────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

## Core Execution Flow

```text
User clicks Run Task
        │
        ▼
React sends prompt + Relay URL + API Key + Model
        │
        ▼
FastAPI creates task_run and starts background agent task
        │
        ├── stores messages / events / screenshots metadata in PostgreSQL
        ├── streams progress to frontend through WebSocket
        ├── saves screenshot files as artifacts
        └── controls VNC desktop through Claude Computer Use
        │
        ▼
VNC window shows the visible execution process
```

## Data Relationship

```text
users
  └── sessions
        ├── task_runs
        │     ├── events      run_id scoped
        │     └── artifacts   run_id scoped screenshots
        └── messages
```

## Notes

- `Run History` is backed by the `task_runs` table.
- Clicking `View` in `Run History` loads one run by `run_id`.
- Timeline events and screenshots are scoped to the selected `run_id`.
- Screenshot files are stored as artifacts, while PostgreSQL stores metadata.
- WebSocket is the primary channel for live task progress.
