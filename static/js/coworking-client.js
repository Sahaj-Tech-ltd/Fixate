/**
 * Fixate Coworking Client
 *
 * Vanilla JS ES module for the Go coworking WebSocket server.
 *
 * Usage:
 *   import { createCoworkingClient } from './coworking-client.js';
 *
 *   const cw = createCoworkingClient();
 *   cw.onPresence((members, count) => { ... });
 *   cw.onChat((msg) => { ... });          // msg = { sender, content, ts }
 *   cw.onTimerSync((state, sender) => { ... });
 *   cw.onJoined((info) => { ... });       // info = { room, member_id, timer }
 *
 *   cw.connect('my-room', 'Alice');
 *   cw.sendChat('Hello!');
 *   cw.syncTimer({ running: true, remaining: 1200, label: 'Focus' });
 *   cw.disconnect();
 */

/**
 * Create a new coworking client instance.
 *
 * @param {string} [baseUrl] – WebSocket base URL. Defaults to the current
 *   page's host with the appropriate ws/wss scheme.  Pass an explicit
 *   URL like "wss://example.com" to override.
 * @returns {object} Client API
 */
export function createCoworkingClient(baseUrl) {
  let ws = null;
  let _roomId = null;
  let _displayName = null;
  let _intentionalClose = false;

  // ── callback registry ──────────────────────────────────────────────
  const handlers = {
    presence: null,
    chat: null,
    timerSync: null,
    joined: null,
    error: null,
  };

  // ── URL builder ────────────────────────────────────────────────────
  function wsUrl(room, name) {
    let base = baseUrl;
    if (!base) {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      base = `${proto}//${location.host}`;
    }
    // strip trailing slash
    base = base.replace(/\/+$/, '');
    return `${base}/ws?room=${encodeURIComponent(room)}&name=${encodeURIComponent(name)}`;
  }

  // ── public API ─────────────────────────────────────────────────────

  /**
   * Connect to a room with the given display name.
   * @param {string} roomId
   * @param {string} displayName
   */
  function connect(roomId, displayName) {
    disconnect(); // close any existing connection
    _roomId = roomId;
    _displayName = displayName;
    _intentionalClose = false;

    const url = wsUrl(roomId, displayName);
    ws = new WebSocket(url);

    ws.onopen = function () {
      console.log('[coworking] connected to room:', roomId);
    };

    ws.onmessage = function (event) {
      var msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        console.error('[coworking] bad json:', e);
        return;
      }
      dispatch(msg);
    };

    ws.onclose = function (ev) {
      console.log('[coworking] closed:', ev.code, ev.reason);
      ws = null;
    };

    ws.onerror = function (ev) {
      console.error('[coworking] ws error', ev);
    };
  }

  /**
   * Disconnect from the current room.
   */
  function disconnect() {
    _intentionalClose = true;
    if (ws) {
      ws.close(1000, 'client disconnect');
      ws = null;
    }
    _roomId = null;
    _displayName = null;
  }

  /**
   * Send a chat message to the room.
   * @param {string} msg – message text
   */
  function sendChat(msg) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'chat', content: msg }));
  }

  /**
   * Broadcast timer state to the room (other members receive a timer_sync event).
   * @param {{ running: boolean, remaining: number, label: string }} state
   */
  function syncTimer(state) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'timer_sync', state: state }));
  }

  // ── event registration ─────────────────────────────────────────────

  /**
   * Called whenever the member list changes.
   * Callback receives (members: Array<{id,name}>, count: number).
   */
  function onPresence(cb) { handlers.presence = cb; }

  /**
   * Called when a chat message arrives.
   * Callback receives ({ sender: string, content: string, ts: number }).
   */
  function onChat(cb) { handlers.chat = cb; }

  /**
   * Called when the shared timer state changes.
   * Callback receives (state: {running,remaining,label}, sender: string).
   */
  function onTimerSync(cb) { handlers.timerSync = cb; }

  /**
   * Called once after a successful join.
   * Callback receives ({ room, member_id, timer }).
   */
  function onJoined(cb) { handlers.joined = cb; }

  /**
   * Called on server-sent errors.
   * Callback receives (message: string).
   */
  function onError(cb) { handlers.error = cb; }

  // ── internal dispatch ──────────────────────────────────────────────

  function dispatch(msg) {
    switch (msg.type) {
      case 'joined':
        if (handlers.joined) handlers.joined(msg);
        break;
      case 'presence':
        if (handlers.presence) handlers.presence(msg.members || [], msg.count || 0);
        break;
      case 'chat':
        if (handlers.chat) handlers.chat(msg);
        break;
      case 'timer_sync':
        if (handlers.timerSync) handlers.timerSync(msg.state, msg.sender);
        break;
      case 'error':
        if (handlers.error) handlers.error(msg.message);
        break;
      default:
        console.warn('[coworking] unknown message type:', msg.type);
    }
  }

  // ── convenience ────────────────────────────────────────────────────

  /** Returns true if the WebSocket is currently open. */
  function isConnected() {
    return ws !== null && ws.readyState === WebSocket.OPEN;
  }

  /** Current room ID (or null). */
  function roomId() { return _roomId; }

  /** Current display name (or null). */
  function displayName() { return _displayName; }

  // ── expose ─────────────────────────────────────────────────────────
  return {
    connect: connect,
    disconnect: disconnect,
    sendChat: sendChat,
    syncTimer: syncTimer,
    onPresence: onPresence,
    onChat: onChat,
    onTimerSync: onTimerSync,
    onJoined: onJoined,
    onError: onError,
    isConnected: isConnected,
    roomId: roomId,
    displayName: displayName
  };

  // Expose globally for non-module script loading
  window.FixateCoworking = { createClient: createCoworkingClient };
  return api;

}
/* Fallback: expose as global for non-module usage */
if (typeof window !== 'undefined' && !window.FixateCoworking) {
    window.FixateCoworking = { createClient: createCoworkingClient };
}
export default createCoworkingClient;
