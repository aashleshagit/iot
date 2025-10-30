"""
Simple Pub/Sub Dashboard (Flask + Socket.IO)

How it works:
- Publishers: POST JSON to /publish  -> {"device_id": "dev1", "topic": "boat/1", "payload": {"temp":22}}
- Server stores last N messages and emits real-time events via Socket.IO.
- Dashboard clients connect via WebSocket, subscribe to topics, and receive messages in real time.

Run:
pip install -r requirements.txt
python app.py

Visit: http://localhost:5000

To expose publicly (cloud), run: python app.py --host 0.0.0.0 --port 5000
"""
import time
import argparse
from datetime import datetime
from collections import deque
from flask import Flask, request, render_template_string, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
MAX_STORED_MESSAGES = int(os.getenv("MAX_STORED_MESSAGES", "500"))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret!")
# CORS allowed for demo; tighten in production
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory store of recent messages (circular)
message_store = deque(maxlen=MAX_STORED_MESSAGES)

# -----------------------
# Utilities
# -----------------------
def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def store_message(msg):
    # msg is a dict; add server timestamp and push to deque
    msg_copy = dict(msg)
    if 'time' not in msg_copy:
        msg_copy['time'] = now_iso()
    message_store.appendleft(msg_copy)

# -----------------------
# HTTP API (Publishers)
# -----------------------
@app.route('/publish', methods=['POST'])
def publish():
    """
    Publisher API:
    POST JSON payload with at least:
    {
      "device_id": "device-1",
      "topic": "boat/1",
      "payload": { "foo": "bar" }
    }

    Optional: "time" (ISO string)
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Expected JSON body"}), 400
    data = request.get_json()

    device_id = data.get('device_id')
    topic = data.get('topic')
    payload = data.get('payload')

    if not device_id or not topic or payload is None:
        return jsonify({"ok": False, "error": "device_id, topic, payload required"}), 400

    msg = {
        "device_id": device_id,
        "topic": topic,
        "payload": payload,
        "time": data.get("time", now_iso())
    }

    # store and broadcast
    store_message(msg)
    # Emit to the specific topic room and to 'global' room
    socketio.emit('message', msg, room=topic)
    socketio.emit('message', msg, room='global')
    return jsonify({"ok": True, "msg": msg}), 200

@app.route('/messages', methods=['GET'])
def get_messages():
    """
    Return recent messages (most recent first).
    Optional query param: topic=xxx to filter by topic prefix
    """
    topic_filter = request.args.get('topic')
    if topic_filter:
        results = [m for m in list(message_store) if m.get('topic','').startswith(topic_filter)]
    else:
        results = list(message_store)
    return jsonify({"messages": results})

# -----------------------
# Socket.IO events (Subscribers / Dashboard)
# -----------------------
@socketio.on('connect')
def handle_connect():
    print(f"[socketio] client connected: {request.sid}")
    emit('connected', {"sid": request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[socketio] client disconnected: {request.sid}")

@socketio.on('subscribe')
def handle_subscribe(data):
    """
    Client sends: {"topic": "boat/1"} to subscribe to that topic.
    Server will join the SocketIO room named after topic.
    """
    topic = data.get('topic')
    if not topic:
        emit('error', {'error': 'topic required for subscribe'})
        return
    join_room(topic)
    emit('subscribed', {'topic': topic})
    # Optionally send last 20 messages for that topic
    recent = [m for m in list(message_store) if m.get('topic','').startswith(topic)][:20]
    emit('recent', {'topic': topic, 'messages': recent})

@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    topic = data.get('topic')
    if not topic:
        emit('error', {'error': 'topic required for unsubscribe'})
        return
    leave_room(topic)
    emit('unsubscribed', {'topic': topic})

@socketio.on('join_global')
def handle_join_global():
    join_room('global')
    emit('joined_global', {})

# -----------------------
# Dashboard UI (simple single-page)
# -----------------------
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <title>Pub/Sub Dashboard</title>
  <meta charset="utf-8" />
  <style>
    body { font-family: Arial, Helvetica, sans-serif; margin: 12px; }
    #left { float:left; width: 360px; margin-right: 12px; }
    #right { margin-left: 380px; }
    .card { border:1px solid #ddd; padding:8px; margin-bottom:8px; border-radius:6px; background:#fafafa; }
    .msg { font-family: monospace; white-space: pre-wrap; }
    #msgs { height: 60vh; overflow:auto; border:1px solid #eee; padding:6px; background:#fff; }
    #topics { margin-bottom:8px; }
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"
    integrity="sha512-DXuhs7nJ8u6b0tC1eYJZrD5vQb1rQjZQ2r1kQ0T0w5+g1s0t0y6qvI1l8QmLQ8eM/7v1Q1m6Kp6k5vG1zY1Q2g=="
    crossorigin="anonymous" referrerpolicy="no-referrer"></script>
</head>
<body>
  <h2>Pub/Sub Dashboard</h2>
  <div id="left">
    <div class="card">
      <h4>Publish (HTTP)</h4>
      <div>
        <label>Device ID</label><br/>
        <input id="pub_device" placeholder="device-1" style="width:100%"/>
      </div>
      <div>
        <label>Topic</label><br/>
        <input id="pub_topic" placeholder="boat/1" style="width:100%"/>
      </div>
      <div>
        <label>JSON Payload</label><br/>
        <textarea id="pub_payload" rows="6" style="width:100%;">{"msg":"hello"}</textarea>
      </div>
      <button onclick="publish()">Publish</button>
      <div id="publish_result" style="margin-top:6px;color:green"></div>
    </div>

    <div class="card">
      <h4>Subscriptions</h4>
      <div id="topics">
        <input id="sub_topic" placeholder="topic to subscribe" style="width:70%"/>
        <button onclick="subscribe()">Subscribe</button>
        <button onclick="unsubscribe()">Unsubscribe</button>
        <button onclick="joinGlobal()">Join Global</button>
      </div>
      <div>
        <strong>Subscribed topics:</strong>
        <ul id="subscribed_list"></ul>
      </div>
    </div>

    <div class="card">
      <h4>Controls</h4>
      <button onclick="loadRecent()">Load recent messages</button>
      <button onclick="clearMessages()">Clear shown messages</button>
      <div style="font-size:12px;margin-top:6px;color:#555">To publish programmatically, POST JSON to /publish</div>
    </div>
  </div>

  <div id="right">
    <div class="card">
      <h4>Live Messages</h4>
      <div id="msgs"></div>
    </div>
  </div>

<script>
  const socket = io();

  const msgsEl = document.getElementById('msgs');
  const subscribedList = document.getElementById('subscribed_list');

  let subscribedTopics = new Set();

  socket.on('connect', () => {
    appendMsg({system: true, text: 'Connected to server (socket id: ' + socket.id + ')' });
  });

  socket.on('connected', d => {
    console.log('connected event', d);
  });

  socket.on('message', (msg) => {
    appendMsg(msg);
  });

  socket.on('recent', (data) => {
    appendMsg({system: true, text: `Recent for topic ${data.topic} (${data.messages.length})`});
    data.messages.reverse().forEach(m => appendMsg(m));
  });

  socket.on('subscribed', d => {
    appendMsg({system:true, text: 'Subscribed to ' + d.topic});
    subscribedTopics.add(d.topic);
    renderSubscribed();
  });

  socket.on('unsubscribed', d => {
    appendMsg({system:true, text: 'Unsubscribed from ' + d.topic});
    subscribedTopics.delete(d.topic);
    renderSubscribed();
  });

  socket.on('joined_global', () => {
    appendMsg({system:true, text: 'Joined global room'});
    subscribedTopics.add('global');
    renderSubscribed();
  });

  function appendMsg(msg) {
    const d = document.createElement('div');
    d.className = 'msg';
    if (msg.system) {
      d.innerText = `[SYSTEM] ${msg.text}`;
      d.style.color = '#555';
    } else {
      const s = `[${msg.time || ''}] [${msg.topic}] [${msg.device_id}]`;
      d.innerText = s + '\\n' + JSON.stringify(msg.payload, null, 2);
    }
    msgsEl.prepend(d); // newest on top
  }

  function publish() {
    const device = document.getElementById('pub_device').value || 'web-client';
    const topic = document.getElementById('pub_topic').value || 'test';
    let payload;
    try {
      payload = JSON.parse(document.getElementById('pub_payload').value);
    } catch (e) {
      alert('Invalid JSON payload: ' + e);
      return;
    }
    fetch('/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ device_id: device, topic: topic, payload: payload })
    }).then(r => r.json()).then(j => {
      if (j.ok) {
        document.getElementById('publish_result').innerText = 'Published ✅';
      } else {
        document.getElementById('publish_result').innerText = 'Error: ' + (j.error || JSON.stringify(j));
      }
    }).catch(err => {
      document.getElementById('publish_result').innerText = 'Network error';
      console.error(err);
    });
  }

  function subscribe() {
    const topic = document.getElementById('sub_topic').value;
    if (!topic) return alert('Enter topic to subscribe');
    socket.emit('subscribe', { topic: topic });
  }

  function unsubscribe() {
    const topic = document.getElementById('sub_topic').value;
    if (!topic) return alert('Enter topic to unsubscribe');
    socket.emit('unsubscribe', { topic: topic });
  }

  function joinGlobal() {
    socket.emit('join_global', {});
  }

  function renderSubscribed() {
    subscribedList.innerHTML = '';
    Array.from(subscribedTopics).forEach(t => {
      const li = document.createElement('li');
      li.innerText = t;
      subscribedList.appendChild(li);
    });
  }

  function loadRecent() {
    fetch('/messages').then(r => r.json()).then(j => {
      appendMsg({system:true, text: 'Loaded recent messages: ' + j.messages.length});
      j.messages.forEach(m => appendMsg(m));
    });
  }

  function clearMessages() {
    msgsEl.innerHTML = '';
  }

</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

# -----------------------
# Command-line / Run server
# -----------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default=os.getenv('HOST', '127.0.0.1'))
    p.add_argument('--port', type=int, default=int(os.getenv('PORT', '5000')))
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    # Use eventlet for production / real-time
    print(f"Starting server on {args.host}:{args.port} (Socket.IO with eventlet)")
    # Bind to host 0.0.0.0 for cloud deployments
    socketio.run(app, host=args.host, port=args.port, debug=True)
