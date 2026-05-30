import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertCircle,
  Bell,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  ExternalLink,
  Eye,
  FileClock,
  FileText,
  Home,
  KeyRound,
  Link,
  Loader2,
  Lock,
  LogIn,
  Maximize2,
  Menu,
  MessageSquare,
  Monitor,
  Plug,
  RefreshCw,
  Send,
  Server,
  Settings,
  Sun,
  UserPlus,
} from 'lucide-react';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || API_BASE_URL.replace(/^http/, 'ws');

function readStoredAuthUser() {
  try {
    const stored = localStorage.getItem('agent-console-auth');
    return stored ? JSON.parse(stored).user : null;
  } catch {
    localStorage.removeItem('agent-console-auth');
    return null;
  }
}

function readStoredAuthToken() {
  try {
    const stored = localStorage.getItem('agent-console-auth');
    return stored ? JSON.parse(stored).token : null;
  } catch {
    localStorage.removeItem('agent-console-auth');
    return null;
  }
}

function authenticatedAssetUrl(path) {
  const token = readStoredAuthToken();
  const separator = path.includes('?') ? '&' : '?';
  return `${API_BASE_URL}${path}${token ? `${separator}token=${encodeURIComponent(token)}` : ''}`;
}

function App() {
  const [authUser, setAuthUser] = useState(readStoredAuthUser);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ username: '', email: '', password: '' });
  const [authState, setAuthState] = useState({ loading: false, error: '' });
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [events, setEvents] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [runHistory, setRunHistory] = useState([]);
  const [selectedRunDetail, setSelectedRunDetail] = useState(null);
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const [vncConnection, setVncConnection] = useState(null);
  const [activeView, setActiveView] = useState('dashboard');
  const [prompt, setPrompt] = useState('Open example.com');
  const [sessionName, setSessionName] = useState('demo-session');
  const [connectionState, setConnectionState] = useState('idle');
  const [apiState, setApiState] = useState({ loading: false, error: '' });
  const [testLoading, setTestLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [relayConfigs, setRelayConfigs] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [relayStatus, setRelayStatus] = useState('idle');
  const socketRef = useRef(null);
  const runAbortRef = useRef(null);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) || null,
    [sessions, activeSessionId],
  );
  const activeRelayConfig = useMemo(
    () => relayConfigs.find((config) => config.api_url === apiUrl) || null,
    [relayConfigs, apiUrl],
  );
  const modelChoices = useMemo(() => {
    const savedModels = activeRelayConfig?.models?.length
      ? activeRelayConfig.models
      : activeRelayConfig?.model
        ? [activeRelayConfig.model]
        : [];
    const choices = Array.from(new Set(savedModels.filter(Boolean)));
    if (selectedModel && !choices.includes(selectedModel)) {
      return [selectedModel, ...choices];
    }
    return choices;
  }, [activeRelayConfig, selectedModel]);

  useEffect(() => {
    if (!authUser) {
      return undefined;
    }
    loadRelayConfig();
    loadSessions();
    loadRunHistory();
    return () => closeSocket();
  }, [authUser]);

  useEffect(() => {
    if (!activeSessionId) {
      return;
    }
    loadSessionDetails(activeSessionId);
    connectWebSocket(activeSessionId);
    return () => closeSocket();
  }, [activeSessionId]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    setRunLoading(activeSession.status === 'running');
  }, [activeSession?.status]);

  async function request(path, options = {}) {
    const token = readStoredAuthToken();
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed with ${response.status}`);
    }
    return response.json();
  }

  async function submitAuth(event) {
    event.preventDefault();
    setAuthState({ loading: true, error: '' });
    try {
      const payload =
        authMode === 'register'
          ? authForm
          : { username: authForm.username, password: authForm.password };
      const data = await request(`/api/auth/${authMode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      localStorage.setItem('agent-console-auth', JSON.stringify(data));
      setAuthUser(data.user);
      setRelayConfigs([]);
      setApiUrl('');
      setApiKey('');
      setSelectedModel('');
      setRelayStatus('idle');
      setAuthState({ loading: false, error: '' });
    } catch (error) {
      setAuthState({ loading: false, error: error.message });
    }
  }

  function updateAuthForm(field, value) {
    setAuthForm((current) => ({ ...current, [field]: value }));
  }

  function signOut() {
    closeSocket();
    localStorage.removeItem('agent-console-auth');
    setAuthUser(null);
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
    setEvents([]);
    setArtifacts([]);
    setVncConnection(null);
    setRelayConfigs([]);
    setApiUrl('');
    setApiKey('');
    setSelectedModel('');
    setRelayStatus('idle');
    setConnectionState('idle');
  }

  async function loadRelayConfig() {
    try {
      const data = await request('/api/relay-config');
      const configs = data.configs || [];
      setRelayConfigs(configs);
      setApiUrl(configs[0]?.api_url || '');
      setApiKey(configs[0]?.api_key || '');
      setSelectedModel('');
      setRelayStatus('idle');
    } catch (error) {
      setRelayStatus('failed');
      setApiState({ loading: false, error: error.message });
    }
  }

  function updateApiUrl(value) {
    setApiUrl(value);
    const matchedConfig = relayConfigs.find((config) => config.api_url === value);
    if (matchedConfig) {
      setApiKey(matchedConfig.api_key || '');
      setSelectedModel('');
      setRelayStatus('idle');
    }
  }

  async function testAndSaveRelayConfig() {
    if (!authUser) {
      return;
    }
    setTestLoading(true);
    setApiState({ loading: false, error: '' });
    try {
      const data = await request('/api/relay-config/test-and-save', {
        method: 'POST',
        body: JSON.stringify({
          api_url: apiUrl,
          api_key: apiKey,
          model: selectedModel,
        }),
      });
      setApiUrl(data.api_url || '');
      setApiKey(data.api_key || '');
      setRelayConfigs((current) => {
        const rest = current.filter((config) => config.api_url !== data.api_url);
        return [data, ...rest];
      });
      setSelectedModel(data.model || '');
      setRelayStatus(data.connection_status || 'success');
      setApiState({ loading: false, error: '' });
    } catch (error) {
      setRelayStatus('failed');
      setApiState({ loading: false, error: error.message });
    } finally {
      setTestLoading(false);
    }
  }

  async function loadSessions() {
    setApiState({ loading: true, error: '' });
    try {
      const data = await request('/api/sessions');
      setSessions(data);
      if (!activeSessionId) {
        if (data.length > 0) {
          setActiveSessionId(data[data.length - 1].id);
        } else {
          await createSessionRecord();
        }
      }
      setApiState({ loading: false, error: '' });
    } catch (error) {
      setApiState({ loading: false, error: error.message });
    }
  }

  async function loadRunHistory() {
    try {
      const data = await request('/api/sessions/history');
      setRunHistory(data);
      return data;
    } catch (error) {
      setApiState({ loading: false, error: error.message });
      return [];
    }
  }

  async function loadSessionDetails(sessionId, runId = activeRunId) {
    try {
      const eventPath = runId
        ? `/api/sessions/${sessionId}/events?run_id=${encodeURIComponent(runId)}`
        : `/api/sessions/${sessionId}/events`;
      const [messageData, eventData, vncData] = await Promise.all([
        request(`/api/sessions/${sessionId}/messages`),
        request(eventPath),
        request(`/api/sessions/${sessionId}/vnc`),
      ]);
      const artifactData = runId
        ? await request(`/api/artifacts/sessions/${sessionId}?run_id=${encodeURIComponent(runId)}`)
        : [];
      setMessages(messageData);
      setEvents(eventData);
      setVncConnection(vncData);
      setArtifacts(artifactData);
    } catch (error) {
      setApiState({ loading: false, error: error.message });
    }
  }

  async function loadRunDetail(run) {
    if (!run?.id) {
      return;
    }
    setHistoryDetailLoading(true);
    setApiState({ loading: false, error: '' });
    try {
      const detail = await request(`/api/sessions/history/${run.id}`);
      setSelectedRunDetail(detail);
      setHistoryDetailLoading(false);
    } catch (error) {
      setHistoryDetailLoading(false);
      setApiState({ loading: false, error: error.message });
    }
  }

  async function createSession(event) {
    event.preventDefault();
    setApiState({ loading: true, error: '' });
    try {
      await createSessionRecord();
      setApiState({ loading: false, error: '' });
    } catch (error) {
      setApiState({ loading: false, error: error.message });
    }
  }

  async function createSessionRecord() {
    closeSocket();
    setConnectionState('connecting');
    setMessages([]);
    setEvents([]);
    setArtifacts([]);
    setActiveRunId(null);
    setVncConnection(null);
    const session = await request('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({ name: sessionName.trim() || null }),
    });
    setSessions((current) => {
      if (current.some((item) => item.id === session.id)) {
        return current.map((item) => (item.id === session.id ? session : item));
      }
      return [...current, session];
    });
    setActiveSessionId(session.id);
    return session;
  }

  async function sendPrompt(event) {
    event.preventDefault();
    const promptValue = prompt.trim();
    if (!promptValue) {
      setApiState({ loading: false, error: 'Enter a task prompt before running.' });
      return;
    }
    if (!apiUrl.trim() || !apiKey.trim()) {
      setApiState({ loading: false, error: 'Enter a Relay API URL and API key before running a task.' });
      return;
    }
    if (!selectedModel) {
      setApiState({ loading: false, error: 'Select a model from the tested Relay API configuration before running.' });
      return;
    }
    const controller = new AbortController();
    runAbortRef.current = controller;
    setRunLoading(true);
    setApiState({ loading: false, error: '' });
    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const session = await createSessionRecord();
        sessionId = session.id;
        await loadSessionDetails(sessionId);
        connectWebSocket(sessionId);
      }
      setArtifacts([]);
      const message = await request(`/api/sessions/${sessionId}/messages`, {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          content: promptValue,
          relay_config_id: activeRelayConfig?.id || null,
          relay_api_url: apiUrl.trim(),
          relay_api_key: apiKey.trim(),
          model: selectedModel,
        }),
      });
      const history = await loadRunHistory();
      const currentRun = history.find((run) => run.message_id === message.id);
      if (currentRun) {
        setActiveRunId(currentRun.id);
        await request(`/api/artifacts/sessions/${sessionId}?run_id=${encodeURIComponent(currentRun.id)}`)
          .then(setArtifacts)
          .catch(() => {});
      }
      const session = await request(`/api/sessions/${sessionId}`);
      setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
      setActiveSessionId(sessionId);
      setApiState({ loading: false, error: '' });
    } catch (error) {
      if (error.name !== 'AbortError') {
        setApiState({ loading: false, error: error.message });
        setRunLoading(false);
      }
    } finally {
      if (runAbortRef.current === controller) {
        runAbortRef.current = null;
      }
    }
  }

  async function cancelRunTask() {
    if (!activeSessionId) {
      return;
    }
    try {
      await request(`/api/sessions/${activeSessionId}/cancel`, { method: 'POST' });
      runAbortRef.current?.abort();
      await Promise.all([loadSessions(), loadSessionDetails(activeSessionId)]);
      await loadRunHistory();
      setApiState({ loading: false, error: '' });
    } catch (error) {
      setApiState({ loading: false, error: error.message });
    } finally {
      setRunLoading(false);
    }
  }

  async function terminateSession() {
    if (!activeSessionId) {
      return;
    }
    setApiState({ loading: true, error: '' });
    try {
      const session = await request(`/api/sessions/${activeSessionId}`, { method: 'DELETE' });
      setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
      setApiState({ loading: false, error: '' });
    } catch (error) {
      setApiState({ loading: false, error: error.message });
    }
  }

  function connectWebSocket(sessionId) {
    closeSocket();
    setConnectionState('connecting');
    const token = encodeURIComponent(readStoredAuthToken() || '');
    const socket = new WebSocket(`${WS_BASE_URL}/ws/sessions/${sessionId}?token=${token}`);
    socketRef.current = socket;

    socket.onopen = () => setConnectionState('connected');
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.type !== 'connected') {
        setEvents((current) => [...current, event]);
        handleRealtimeEvent(sessionId, event);
      }
    };
    socket.onerror = () => setConnectionState('error');
    socket.onclose = () => {
      if (socketRef.current === socket) {
        setConnectionState('closed');
      }
    };
  }

  function closeSocket() {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }

  function handleRealtimeEvent(sessionId, event) {
    if (event.type === 'screenshot') {
      const runId = event.payload?.run_id || activeRunId;
      if (runId) {
        request(`/api/artifacts/sessions/${sessionId}?run_id=${encodeURIComponent(runId)}`)
          .then(setArtifacts)
          .catch(() => {});
      }
    }
    if (event.type !== 'completed' && event.type !== 'error') {
      return;
    }

    setRunLoading(false);
    request(`/api/sessions/${sessionId}`)
      .then((session) => {
        setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
      })
      .catch(() => {});
    loadSessionDetails(sessionId, event.payload?.run_id || activeRunId).catch(() => {});
    loadRunHistory().catch(() => {});
  }

  const currentModel = selectedModel || '--';
  const lastEvent = events[events.length - 1];
  const responseTime = lastEvent ? '842 ms' : '--';
  const canRunTask = !runLoading;
  const screenshotArtifacts = artifacts.filter((artifact) => artifact.kind === 'screenshot');
  const displayedEvents = activeRunId
    ? events.filter((event) => event.run_id === activeRunId || event.payload?.run_id === activeRunId)
    : [];

  if (!authUser) {
    return (
      <AuthScreen
        mode={authMode}
        form={authForm}
        state={authState}
        onModeChange={setAuthMode}
        onChange={updateAuthForm}
        onSubmit={submitAuth}
      />
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">C</div>
          <strong>Relay Console</strong>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          <NavItem active={activeView === 'dashboard'} icon={<Home size={20} />} label="Dashboard" onClick={() => setActiveView('dashboard')} />
          <NavItem active={activeView === 'history'} icon={<FileClock size={20} />} label="Run History" onClick={() => setActiveView('history')} />
          <NavItem icon={<Settings size={20} />} label="Models" />
        </nav>
        <div className="sidebar-footer">
          <FileText size={19} />
          <span>Documentation</span>
          <ExternalLink size={16} />
        </div>
      </aside>

      <section className="workspace">
        <header className="app-topbar">
          <button className="plain-icon" type="button" aria-label="Toggle menu">
            <Menu size={22} />
          </button>
          <div className="topbar-actions">
            <button className="plain-icon" type="button" aria-label="Toggle theme">
              <Sun size={20} />
            </button>
            <button className="plain-icon has-badge" type="button" aria-label="Notifications">
              <Bell size={20} />
              <span>3</span>
            </button>
            <button className="plain-icon" type="button" aria-label="Help">
              <CircleHelp size={20} />
            </button>
            <div className="user-menu">
              <span>{authUser.username.slice(0, 1).toUpperCase()}</span>
              <strong>{authUser.username}</strong>
              <ChevronDown size={16} />
            </div>
            <button className="outline-button compact" type="button" onClick={signOut}>
              Sign out
            </button>
          </div>
        </header>

        <div className="page-title-row">
          <div>
            <h1>Relay Connection and Execution</h1>
            <p>Configure the API relay, test connectivity, select a model, and run tasks.</p>
          </div>
          <StepProgress />
        </div>

        {apiState.error && (
          <div className="alert" role="alert">
            <AlertCircle size={18} />
            {apiState.error}
          </div>
        )}

        {activeView === 'history' ? (
          <RunHistoryView
            history={runHistory}
            selectedRunDetail={selectedRunDetail}
            loadingDetail={historyDetailLoading}
            onRefresh={loadRunHistory}
            onSelectRun={loadRunDetail}
          />
        ) : (
          <>
        <section className="connection-card">
          <SectionTitle icon={<Link size={21} />} title="Connection Settings" />
          <div className="connection-grid">
            <Field label="Relay API URL">
              <div className="field-control">
                <Link size={17} />
                <input
                  value={apiUrl}
                  onChange={(event) => updateApiUrl(event.target.value)}
                  placeholder="Enter API URL"
                  list="relay-api-url-options"
                />
                <datalist id="relay-api-url-options">
                  {relayConfigs.map((config) => (
                    <option key={config.id || config.api_url} value={config.api_url} />
                  ))}
                </datalist>
              </div>
            </Field>
            <Field label="Relay API Key">
              <div className="field-control">
                <KeyRound size={17} />
                <input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Enter relay API key"
                  type="password"
                />
                <Eye size={17} />
              </div>
            </Field>
            <Field label="">
              <button className="test-button" type="button" onClick={testAndSaveRelayConfig} disabled={testLoading}>
                {testLoading ? <Loader2 className="spin" size={18} /> : <Activity size={18} />}
                Test
              </button>
            </Field>
            <Field label="Connection Status">
              <div className={`connection-state ${relayStatus}`}>
                {relayStatus === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                <strong>{relayStatus === 'success' ? 'Connected' : relayStatus === 'failed' ? 'Failed' : 'Not Tested'}</strong>
              </div>
            </Field>
            <Field label="">
              <label className="select-wrap">
                <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                  <option value="">Select a model</option>
                  {modelChoices.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
                <ChevronDown size={18} />
              </label>
            </Field>
          </div>
        </section>

        <section className="content-grid">
          <section className="task-card">
            <div className="card-title-row">
              <SectionTitle icon={<FileText size={21} />} title="Task Input" />
              <button className="ghost-button" type="button" onClick={loadSessions}>
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>

            <form className="session-form" onSubmit={createSession}>
              <label htmlFor="session-name">Session Name</label>
              <div className="session-row">
                <input
                  id="session-name"
                  value={sessionName}
                  onChange={(event) => setSessionName(event.target.value)}
                  placeholder="demo-session"
                />
                <button className="outline-button" type="submit">
                  New
                </button>
              </div>
            </form>

            <form className="composer" onSubmit={sendPrompt}>
              <label htmlFor="prompt">Prompt</label>
              <textarea
                id="prompt"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Enter the task prompt to send through the relay..."
              />
              <div className="execution-note">
                This prompt will be sent to the selected relay model:
                <strong>{currentModel}</strong>
                .
              </div>
              <div className="button-row task-actions">
                <button className="primary-button" type="submit" disabled={!canRunTask}>
                  {runLoading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
                  Run Task
                </button>
                <button className="cancel-button" type="button" onClick={cancelRunTask} disabled={!runLoading}>
                  Cancel
                </button>
              </div>
            </form>

            <div className="stats-strip">
              <Stat icon={<Server size={22} />} label="Current Model" value={currentModel} />
              <Stat icon={<CheckCircle2 size={22} />} label="Latest Run" value={activeSession?.status || 'Pending'} good />
              <Stat icon={<Clock3 size={22} />} label="Latency" value={responseTime} />
            </div>
          </section>

          <section className="vnc-card">
            <div className="vnc-card-header">
              <SectionTitle icon={<Monitor size={22} />} title="VNC Session Window" />
              <div className="vnc-actions">
                <StatusPill state={connectionState} />
                <button
                  className="outline-button compact"
                  type="button"
                  onClick={() => activeSessionId && loadSessionDetails(activeSessionId)}
                  disabled={!activeSessionId}
                >
                  <Plug size={16} />
                  Connect
                </button>
                <button className="danger-soft" type="button" onClick={terminateSession} disabled={!activeSessionId}>
                  Disconnect
                </button>
              </div>
            </div>
            <VncPanel
              key={vncConnection?.session_id || 'empty-vnc'}
              connection={vncConnection}
              screenshots={screenshotArtifacts}
              events={displayedEvents}
            />
          </section>

        </section>
          </>
        )}
      </section>
    </main>
  );
}

function AuthScreen({ mode, form, state, onModeChange, onChange, onSubmit }) {
  const isRegister = mode === 'register';
  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>Relay Console</strong>
            <span>API Relay Agent Console</span>
          </div>
        </div>

        <div className="auth-copy">
          <h1>{isRegister ? 'Create Console Account' : 'Sign In to Console'}</h1>
          <p>Manage relay connections, run tasks, and inspect the VNC remote desktop after signing in.</p>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button className={!isRegister ? 'active' : ''} type="button" onClick={() => onModeChange('login')}>
            <LogIn size={17} />
            Sign In
          </button>
          <button className={isRegister ? 'active' : ''} type="button" onClick={() => onModeChange('register')}>
            <UserPlus size={17} />
            Register
          </button>
        </div>

        {state.error && (
          <div className="alert" role="alert">
            <AlertCircle size={18} />
            {state.error}
          </div>
        )}

        <form className="auth-form" onSubmit={onSubmit}>
          <label htmlFor="auth-username">Username</label>
          <div className="field-control">
            <KeyRound size={17} />
            <input
              id="auth-username"
              value={form.username}
              onChange={(event) => onChange('username', event.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              required
              minLength={3}
            />
          </div>

          {isRegister && (
            <>
              <label htmlFor="auth-email">Email</label>
              <div className="field-control">
                <MessageSquare size={17} />
                <input
                  id="auth-email"
                  value={form.email}
                  onChange={(event) => onChange('email', event.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                />
              </div>
            </>
          )}

          <label htmlFor="auth-password">Password</label>
          <div className="field-control">
            <Lock size={17} />
            <input
              id="auth-password"
              value={form.password}
              onChange={(event) => onChange('password', event.target.value)}
              placeholder="At least 6 characters"
              type="password"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              required
              minLength={6}
            />
          </div>

          <button className="primary-button auth-submit" type="submit" disabled={state.loading}>
            {state.loading ? <Loader2 className="spin" size={18} /> : isRegister ? <UserPlus size={18} /> : <LogIn size={18} />}
            {isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>
      </section>
    </main>
  );
}

function NavItem({ icon, label, active = false, onClick }) {
  return (
    <button className={`nav-item ${active ? 'active' : ''}`} type="button" onClick={onClick}>
      {icon}
      {label}
    </button>
  );
}

function RunHistoryView({ history, selectedRunDetail, loadingDetail, onRefresh, onSelectRun }) {
  return (
    <section className="history-card run-history-card">
      <div className="card-title-row">
        <SectionTitle icon={<FileClock size={21} />} title="Run History" />
        <button className="ghost-button" type="button" onClick={onRefresh}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>
      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Session</th>
              <th>Prompt</th>
              <th>Response Time</th>
              <th>Result</th>
              <th>Model</th>
              <th>Base URL</th>
              <th>Error</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {history.length ? (
              history.map((item) => (
                <tr
                  className={selectedRunDetail?.run?.id === item.id ? 'selected' : ''}
                  key={item.id || `${item.session_id}-${item.started_at}`}
                >
                  <td>{formatDateTime(item.started_at)}</td>
                  <td>{item.session_id ? item.session_id.slice(0, 8) : '--'}</td>
                  <td>{item.prompt}</td>
                  <td>{formatDuration(item.response_time_ms)}</td>
                  <td>
                    <span className={`result-badge ${item.result}`}>{item.result}</span>
                  </td>
                  <td>{item.model || '--'}</td>
                  <td>{item.base_url || '--'}</td>
                  <td>{item.error || '--'}</td>
                  <td>
                    <button className="outline-button compact" type="button" onClick={() => onSelectRun(item)}>
                      View
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="9" className="table-empty">No run history yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <RunHistoryDetail detail={selectedRunDetail} loading={loadingDetail} />
    </section>
  );
}

function RunHistoryDetail({ detail, loading }) {
  if (loading) {
    return (
      <section className="run-detail-panel">
        <div className="detail-loading">
          <Loader2 className="spin" size={18} />
          Loading run detail
        </div>
      </section>
    );
  }
  if (!detail) {
    return (
      <section className="run-detail-panel">
        <div className="screenshot-empty">Select a run to review its timeline and screenshots.</div>
      </section>
    );
  }

  const screenshots = (detail.artifacts || []).filter((artifact) => artifact.kind === 'screenshot');
  const artifactByEventId = new Map(screenshots.map((artifact) => [artifact.event_id, artifact]));
  const artifactByToolUseId = new Map(
    screenshots.filter((artifact) => artifact.tool_use_id).map((artifact) => [artifact.tool_use_id, artifact]),
  );
  const events = (detail.events || []).filter(isExecutionEvent);

  return (
    <section className="run-detail-panel">
      <header className="run-detail-header">
        <div>
          <strong>Run Detail</strong>
          <p>{detail.run.prompt}</p>
        </div>
        <span className={`result-badge ${detail.run.result}`}>{detail.run.result}</span>
      </header>
      <div className="run-detail-grid">
        <div>
          <small>Started</small>
          <strong>{formatDateTime(detail.run.started_at)}</strong>
        </div>
        <div>
          <small>Response Time</small>
          <strong>{formatDuration(detail.run.response_time_ms)}</strong>
        </div>
        <div>
          <small>Model</small>
          <strong>{detail.run.model || '--'}</strong>
        </div>
        <div>
          <small>Screenshots</small>
          <strong>{screenshots.length}</strong>
        </div>
      </div>
      {detail.run.error && <div className="run-detail-error">{detail.run.error}</div>}
      <ScreenshotTimeline screenshots={[...screenshots].reverse()} />
      <ExecutionSteps events={events} artifactByEventId={artifactByEventId} artifactByToolUseId={artifactByToolUseId} />
    </section>
  );
}

function StepProgress() {
  const steps = [
    ['1', 'Connection Info', 'Enter URL and API key'],
    ['2', 'Test Connection', 'Verify relay availability'],
    ['3', 'Select Model', 'Load available models'],
    ['4', 'Run Task', 'Send prompt and receive results'],
  ];
  return (
    <div className="stepper">
      {steps.map(([number, title, description], index) => (
        <React.Fragment key={number}>
          <div className={`step ${index < 3 ? 'active' : ''}`}>
            <span>{number}</span>
            <div>
              <strong>{title}</strong>
              <small>{description}</small>
            </div>
          </div>
          {index < steps.length - 1 && <ChevronDown className="step-divider" size={18} />}
        </React.Fragment>
      ))}
    </div>
  );
}

function SectionTitle({ icon, title }) {
  return (
    <div className="section-title">
      {icon}
      <h2>{title}</h2>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="field">
      <span>{label}</span>
      {children}
    </div>
  );
}

function Stat({ icon, label, value, good = false }) {
  return (
    <div className="stat">
      <span className={good ? 'good' : ''}>{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function StatusPill({ state }) {
  const connected = state === 'connected';
  return (
    <span className={`status-pill ${connected ? 'online' : ''}`}>
      <span />
      {connected ? 'Online' : state}
    </span>
  );
}

function VncPanel({ connection, screenshots, events }) {
  if (!connection) {
    return <EmptyState text="Select a session to load the VNC window" />;
  }
  const artifactByEventId = new Map(screenshots.map((artifact) => [artifact.event_id, artifact]));
  const artifactByToolUseId = new Map(
    screenshots.filter((artifact) => artifact.tool_use_id).map((artifact) => [artifact.tool_use_id, artifact]),
  );
  const executionSteps = events.filter(isExecutionEvent).slice(-8);
  const recentScreenshots = [...screenshots].slice(-6).reverse();

  return (
    <div className="vnc-content">
      {connection.url ? (
        <>
          <div className="vnc-workbench">
            <iframe className="vnc-frame" title="Session VNC" src={connection.view_only_url || connection.url} />
            <ExecutionSteps
              events={executionSteps}
              artifactByEventId={artifactByEventId}
              artifactByToolUseId={artifactByToolUseId}
            />
          </div>
          <div className="vnc-hint">
            <span>
              <CircleHelp size={17} />
              The VNC desktop also opens an Agent Execution Log terminal inside the remote screen.
            </span>
            <a className="outline-button compact" href={connection.url} target="_blank" rel="noreferrer">
              <Maximize2 size={16} />
              Full Screen
            </a>
          </div>
          <ScreenshotTimeline screenshots={recentScreenshots} />
        </>
      ) : (
        <EmptyState text="VNC is currently unavailable" />
      )}
    </div>
  );
}

function ExecutionSteps({ events, artifactByEventId, artifactByToolUseId }) {
  return (
    <aside className="execution-steps" aria-label="Execution steps">
      <header>
        <strong>Execution Steps</strong>
        <span>{events.length ? `${events.length} recent` : 'idle'}</span>
      </header>
      <div className="step-log">
        {events.length ? (
          events.map((event) => {
            const artifact = screenshotArtifactForEvent(event, artifactByEventId, artifactByToolUseId);
            return (
              <div className={`step-log-row ${event.type}`} key={event.id || `${event.type}-${event.created_at}`}>
                <span className="step-dot" />
                <div>
                  <strong>{eventLabel(event)}</strong>
                  <p>{eventSummary(event)}</p>
                  {artifact && (
                    <img
                      className="step-screenshot"
                      src={authenticatedAssetUrl(artifact.url)}
                      alt={`Screenshot captured at ${formatTime(artifact.created_at)}`}
                    />
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div className="step-log-empty">Run a task to show live steps here.</div>
        )}
      </div>
    </aside>
  );
}

function ScreenshotTimeline({ screenshots }) {
  return (
    <section className="screenshot-timeline" aria-label="Screenshot timeline">
      <header>
        <strong>Screenshot Timeline</strong>
        <span>{screenshots.length ? `${screenshots.length} recent` : 'empty'}</span>
      </header>
      {screenshots.length ? (
        <div className="screenshot-strip">
          {screenshots.map((screenshot, index) => (
            <article className="screenshot-card" key={screenshot.id}>
              <div>
                <strong>Shot {screenshots.length - index}</strong>
                <time>{formatTime(screenshot.created_at)}</time>
              </div>
              <img src={authenticatedAssetUrl(screenshot.url)} alt={`Task screenshot ${screenshots.length - index}`} />
            </article>
          ))}
        </div>
      ) : (
        <div className="screenshot-empty">Screenshots captured by Computer Use will appear here.</div>
      )}
    </section>
  );
}

function screenshotArtifactForEvent(event, artifactByEventId, artifactByToolUseId) {
  if (event.type !== 'screenshot') {
    return null;
  }
  const payload = event.payload || {};
  if (event.id && artifactByEventId.has(event.id)) {
    return artifactByEventId.get(event.id);
  }
  if (payload.tool_use_id && artifactByToolUseId.has(payload.tool_use_id)) {
    return artifactByToolUseId.get(payload.tool_use_id);
  }
  if (payload.artifact_url) {
    return {
      id: payload.artifact_id || event.id,
      url: payload.artifact_url,
      created_at: event.created_at,
    };
  }
  return null;
}

function isExecutionEvent(event) {
  return ['user_message', 'agent_message', 'tool_started', 'tool_result', 'screenshot', 'completed', 'error'].includes(event.type);
}

function eventLabel(event) {
  const labels = {
    user_message: 'Prompt',
    agent_message: 'Agent',
    tool_started: 'Tool Call',
    tool_result: 'Tool Result',
    screenshot: 'Screenshot',
    completed: 'Completed',
    error: 'Error',
  };
  return labels[event.type] || event.type;
}

function eventSummary(event) {
  const payload = event.payload || {};
  if (event.type === 'user_message') {
    return payload.content || '';
  }
  if (event.type === 'agent_message') {
    const content = payload.content;
    if (typeof content === 'string') {
      return content;
    }
    return content?.thinking || content?.text || JSON.stringify(content || {});
  }
  if (event.type === 'tool_started') {
    return `${payload.tool || 'tool'} ${JSON.stringify(payload.input || {})}`;
  }
  if (event.type === 'tool_result') {
    return payload.error || (payload.has_image ? 'Screenshot captured' : payload.output || 'Done');
  }
  if (event.type === 'screenshot') {
    return payload.artifact_url ? 'Image saved' : 'Image captured';
  }
  if (event.type === 'completed') {
    return 'Task finished';
  }
  if (event.type === 'error') {
    return payload.message || 'Execution failed';
  }
  return JSON.stringify(payload);
}

function EmptyState({ text }) {
  return <div className="empty-state">{text}</div>;
}

function formatTime(value) {
  if (!value) {
    return '';
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) {
    return '--';
  }
  return new Intl.DateTimeFormat(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function formatDuration(value) {
  if (value === null || value === undefined) {
    return '--';
  }
  if (value < 1000) {
    return `${value} ms`;
  }
  return `${(value / 1000).toFixed(1)} s`;
}

createRoot(document.getElementById('root')).render(<App />);
