from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# In-memory message and subscription store
messages = []
subscribers = {}  # {topic: [list of subscribers]}

# HTML template
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>IoT Publish–Subscribe Dashboard</title>
    <style>
        body { font-family: Arial; text-align: center; background-color: #f2f2f2; }
        h1 { color: #2d89ef; }
        .container { width: 80%; margin: auto; background: white; padding: 20px;
                     border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        input, button { padding: 8px; margin: 5px; border-radius: 5px; border: 1px solid #ccc; }
        button { background: #2d89ef; color: white; border: none; cursor: pointer; }
        button:hover { background: #1b5fbf; }
        .section { margin-top: 25px; text-align: left; }
        .msg { background: #e1f5fe; margin: 5px 0; padding: 8px; border-radius: 8px; }
        .topic { font-weight: bold; color: #0a58ca; }
    </style>
</head>
<body>
    <div class="container">
        <h1>IoT Publish–Subscribe Dashboard</h1>

        <div class="section">
            <h2>🔹 Publisher Section</h2>
            <form id="publishForm">
                <input type="text" id="pubTopic" placeholder="Enter Topic (e.g. temperature)" required>
                <input type="text" id="pubMessage" placeholder="Enter Message (e.g. 28°C)" required>
                <button type="submit">Publish</button>
            </form>
        </div>

        <div class="section">
            <h2>🔸 Subscriber Section</h2>
            <form id="subscribeForm">
                <input type="text" id="subName" placeholder="Subscriber Name" required>
                <input type="text" id="subTopic" placeholder="Topic to Subscribe" required>
                <button type="submit">Subscribe</button>
            </form>
        </div>

        <div class="section">
            <h2>📡 Live Messages</h2>
            <div id="messages"></div>
        </div>
    </div>

    <script>
        // Fetch and show all messages
        async function fetchMessages() {
            const res = await fetch('/messages');
            const data = await res.json();
            const box = document.getElementById('messages');
            box.innerHTML = '';
            data.forEach(m => {
                box.innerHTML += `<div class='msg'><span class='topic'>${m.topic}</span>: ${m.message}</div>`;
            });
        }

        // Publish new message
        document.getElementById('publishForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const topic = document.getElementById('pubTopic').value;
            const message = document.getElementById('pubMessage').value;

            await fetch('/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `topic=${topic}&message=${message}`
            });

            document.getElementById('pubTopic').value = '';
            document.getElementById('pubMessage').value = '';
            fetchMessages();
        });

        // Subscribe to a topic
        document.getElementById('subscribeForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('subName').value;
            const topic = document.getElementById('subTopic').value;

            await fetch('/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${name}&topic=${topic}`
            });

            alert(`${name} subscribed to topic '${topic}'`);
            document.getElementById('subName').value = '';
            document.getElementById('subTopic').value = '';
        });

        // Refresh messages every 2 seconds
        setInterval(fetchMessages, 2000);
        fetchMessages();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(dashboard_html)

# ✅ Publisher endpoint
@app.route('/publish', methods=['POST'])
def publish():
    topic = request.form.get('topic')
    message = request.form.get('message')

    if not topic or not message:
        return jsonify({'error': 'Topic and message required'}), 400

    messages.append({'topic': topic, 'message': message})

    # Notify subscribers (simulation)
    if topic in subscribers:
        for sub in subscribers[topic]:
            print(f"🔔 Notification sent to {sub} for topic '{topic}': {message}")

    return jsonify({'status': 'Message published successfully', 'topic': topic, 'message': message})

# ✅ Subscriber endpoint
@app.route('/subscribe', methods=['POST'])
def subscribe():
    name = request.form.get('name')
    topic = request.form.get('topic')

    if not name or not topic:
        return jsonify({'error': 'Subscriber name and topic required'}), 400

    if topic not in subscribers:
        subscribers[topic] = []
    if name not in subscribers[topic]:
        subscribers[topic].append(name)

    return jsonify({'status': f'{name} subscribed to {topic}'})

# ✅ Fetch messages endpoint
@app.route('/messages', methods=['GET'])
def get_messages():
    return jsonify(messages)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
