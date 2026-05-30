# Project Introduction Script

## 中文介绍

大家好，下面我来介绍这个项目。

这个项目是一个面向 Claude Computer Use 场景的全栈 Agent 控制台。它的目标是让用户可以在浏览器中配置 Relay API、选择模型、输入任务 Prompt，然后通过后端 Agent Runner 调用 Claude Computer Use，在远程 VNC 虚拟桌面中可视化地执行任务。执行过程中，系统会实时展示任务状态、工具调用、截图、执行日志和历史记录。

从技术架构上看，项目采用 Docker Compose 进行整体编排，主要包括 React 前端、FastAPI 后端、PostgreSQL 数据库、nginx 反向代理，以及 noVNC 虚拟桌面服务。用户访问 `http://127.0.0.1/` 时，首先进入 nginx，再由 nginx 代理到 React 前端。前端通过 HTTP 和 WebSocket 与 FastAPI 后端通信。后端负责用户登录鉴权、Relay 配置管理、任务执行、事件推送、截图保存和 VNC 控制。PostgreSQL 负责保存用户、会话、任务运行记录、事件、截图元数据以及 Relay 配置信息。

代码结构上，后端按照职责进行了比较清晰的分层。`app/api` 目录负责 HTTP 和 WebSocket 接口，例如登录注册、Session 管理、Run Task、Run History、Artifact 文件访问等。`app/services` 目录负责核心业务逻辑，包括 Agent Runner、Session Manager、Relay Config、Artifact Service、VNC Service、WebSocket Manager、任务取消和执行控制。`app/db` 目录负责数据库模型和初始化迁移。`app/schemas` 目录则定义了接口输入输出的数据结构。前端主要集中在 `frontend/src`，负责登录页面、Relay 配置、任务输入、VNC 窗口、执行步骤、截图时间线和 Run History 详情展示。

项目的核心执行流程是这样的：用户登录后，输入 Relay API URL、API Key，并通过 Test 按钮测试连接。测试通过后，用户选择模型并输入 Prompt，点击 Run Task。后端会创建一条独立的 `task_run` 记录，然后后台异步启动 Agent Runner。Agent Runner 使用当前用户输入的 Relay URL、API Key 和模型执行任务，而不是固定读取环境变量。执行过程中，所有事件都会写入 `events` 表，并通过 WebSocket 实时推送给前端。如果 Computer Use 工具返回截图，后端会将截图保存为 artifact 文件，同时把截图元数据保存到 PostgreSQL。前端会根据当前 `run_id` 只展示本次任务产生的事件和截图。

这个项目的一个重要特点是可视化执行。任务不是只在后端静默运行，而是会在 VNC 虚拟桌面中展示执行过程。用户可以在浏览器中看到远程桌面，并观察任务是否真的打开了终端、浏览器或者其他 GUI 程序。同时，VNC 中还有执行日志窗口，用来显示当前任务步骤和命令结果。

第二个优势是实时性。项目使用 WebSocket 作为任务执行的主流程反馈通道。Run Task 请求被后端接受后会快速返回，真正的执行状态、截图、工具调用、完成或失败事件都通过 WebSocket 推送。这种设计避免了前端长时间等待 HTTP 请求，也更适合 Agent 这类长时间、多步骤的任务。

第三个优势是数据可追踪。每次点击 Run Task 都会生成独立的 `task_run`。事件和截图都通过 `run_id` 关联到具体的一次运行，所以 Run History 可以准确回看某一次任务，而不会和同一个 Session 里的其他任务混在一起。用户点击历史记录中的 View，可以看到那一次任务的 Prompt、模型、响应时间、结果、错误信息、截图时间线和执行步骤。

第四个优势是安全性和工程完整性。项目实现了 JWT 登录鉴权，后端根据 token 解析当前用户，不依赖前端传来的 user_id。Relay API Key 采用加密方式存储，避免明文持久化。接口也会校验资源归属，用户只能访问自己的 Session、Run History 和 Artifact 文件。此外，项目有 Docker Compose 一键部署能力，并配套了接口文档、WebSocket/timeline 说明、架构图和测试用例。

最后，这个项目和普通的聊天应用不同，它更接近一个 Computer Use Agent 执行平台。它不仅能发送 Prompt，还能展示模型调用工具的过程、保存截图证据、回放历史任务，并让用户通过 VNC 看到实际桌面执行效果。整体来说，它具备较完整的后端设计、实时流式反馈、可观测执行过程、持久化记录和容器化部署能力。

以上就是这个项目的介绍。

## English Introduction

Hello everyone. I will introduce this project.

This project is a full-stack Agent console designed for Claude Computer Use scenarios. Its goal is to allow users to configure a Relay API, select a model, enter a task prompt, and then run the task through a backend Agent Runner. The Agent uses Claude Computer Use to operate a remote VNC desktop, so the user can visually observe the execution process in the browser. During execution, the system streams task status, tool calls, screenshots, logs, and run history.

From the architecture perspective, the project is orchestrated by Docker Compose. It contains a React frontend, a FastAPI backend, a PostgreSQL database, an nginx reverse proxy, and a noVNC virtual desktop service. When the user opens `http://127.0.0.1/`, the request first reaches nginx, and nginx proxies it to the React frontend. The frontend communicates with the FastAPI backend through HTTP and WebSocket. The backend handles authentication, Relay configuration, task execution, event streaming, screenshot persistence, and VNC control. PostgreSQL stores users, sessions, task runs, events, artifact metadata, and Relay configuration records.

The backend code is organized by responsibility. The `app/api` directory contains HTTP and WebSocket endpoints, such as authentication, session management, Run Task, Run History, and artifact file access. The `app/services` directory contains the core business logic, including the Agent Runner, Session Manager, Relay Config Service, Artifact Service, VNC Service, WebSocket Manager, task cancellation, and execution control. The `app/db` directory defines database models and schema initialization. The `app/schemas` directory defines request and response data models. On the frontend side, `frontend/src` implements the login screen, Relay settings, task input, VNC window, execution steps, screenshot timeline, and Run History detail view.

The core execution flow is straightforward. After login, the user enters a Relay API URL and API key, and clicks the Test button to verify connectivity. After the connection test succeeds, the user selects a model, enters a prompt, and clicks Run Task. The backend creates a new `task_run` record and starts the Agent Runner in the background. The Agent Runner uses the Relay URL, API key, and model provided by the current user, instead of relying only on environment variables. During execution, all events are stored in the `events` table and streamed to the frontend over WebSocket. If the Computer Use tool returns a screenshot, the backend saves the image as an artifact file and stores its metadata in PostgreSQL. The frontend then uses the current `run_id` to show only the events and screenshots produced by that specific task run.

One major advantage of this project is visible execution. The task does not only run silently on the backend. It is executed inside a VNC virtual desktop, so the user can watch whether the agent actually opens a terminal, launches a browser, or interacts with a GUI application. The VNC desktop also includes an execution log window that displays task steps and command results.

The second advantage is real-time feedback. The project uses WebSocket as the primary progress channel. After the backend accepts a Run Task request, the HTTP request returns quickly, while actual progress, screenshots, tool calls, completion events, and error events are pushed through WebSocket. This design avoids long blocking HTTP requests and is a better fit for long-running, multi-step Agent workflows.

The third advantage is traceability. Every Run Task action creates a separate `task_run`. Events and screenshots are linked to that run through `run_id`, so Run History can accurately replay a single execution without mixing it with other tasks in the same session. When the user clicks View in Run History, the UI shows the prompt, model, response time, result, error message, screenshot timeline, and execution steps for that specific run.

The fourth advantage is security and engineering completeness. The project implements JWT-based authentication, and the backend derives the current user from the token instead of trusting a frontend-provided user ID. Relay API keys are encrypted before being stored. The API also checks resource ownership, so users can only access their own sessions, run history, and artifact files. In addition, the project includes Docker Compose deployment, API documentation, WebSocket and timeline documentation, architecture diagrams, and automated tests.

Overall, this project is more than a simple chat application. It is closer to a Computer Use Agent execution platform. It can send prompts, display tool execution, persist screenshot evidence, replay historical runs, and show the actual desktop behavior through VNC. In summary, the project demonstrates solid backend design, real-time streaming, observable execution, persistent records, and containerized deployment.

That is the introduction to this project.
