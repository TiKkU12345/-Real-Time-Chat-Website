from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
from datetime import datetime

print("Importing modules... ✓")

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

print("Flask app created... ✓")

# Initialize SocketIO with simpler config
socketio = SocketIO(app, cors_allowed_origins="*")

print("SocketIO initialized... ✓")

# Store active users and their rooms
active_users = {}
waiting_users = []
active_rooms = {}

@app.route('/')
def index():
    print("Index route accessed")
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f'✓ User {request.sid} connected successfully')
    emit('connected', {'status': 'Connected to server!'})

@socketio.on('disconnect')
def on_disconnect():
    user_id = request.sid
    print(f'✗ User {user_id} disconnected')
    
    # Remove from waiting list
    if user_id in waiting_users:
        waiting_users.remove(user_id)
        print(f"  - Removed {user_id} from waiting list")
    
    # Handle room cleanup
    if user_id in active_users:
        room_id = active_users[user_id].get('room')
        if room_id and room_id in active_rooms:
            # Notify the other user
            other_users = [uid for uid in active_rooms[room_id] if uid != user_id]
            for other_user in other_users:
                emit('user_disconnected', room=other_user)
            
            # Clean up room
            if user_id in active_rooms[room_id]:
                active_rooms[room_id].remove(user_id)
            if len(active_rooms[room_id]) == 0:
                del active_rooms[room_id]
                print(f"  - Cleaned up room {room_id}")
        
        del active_users[user_id]

@socketio.on('find_chat')
def on_find_chat(data):
    user_id = request.sid
    username = data.get('username', f'User_{user_id[:8]}')
    
    active_users[user_id] = {
        'username': username,
        'room': None
    }
    
    print(f'🔍 {username} ({user_id[:8]}) looking for chat...')
    print(f'   Current waiting users: {len(waiting_users)}')
    
    if len(waiting_users) > 0:
        # Match with waiting user
        other_user = waiting_users.pop(0)
        room_id = str(uuid.uuid4())[:8]  # Shorter room ID for easier debugging
        
        # Add both users to room
        join_room(room_id, user_id)
        join_room(room_id, other_user)
        
        # Update user info
        active_users[user_id]['room'] = room_id
        active_users[other_user]['room'] = room_id
        
        # Track room
        active_rooms[room_id] = [user_id, other_user]
        
        other_username = active_users[other_user]['username']
        
        print(f'🎉 MATCH! {username} ↔ {other_username} in room {room_id}')
        
        # Notify both users they found a chat
        emit('chat_found', {
            'room_id': room_id,
            'partner': other_username
        }, room=user_id)
        
        emit('chat_found', {
            'room_id': room_id,
            'partner': username
        }, room=other_user)
        
        # Send admin welcome message to both users after a small delay
        admin_message = {
            'username': 'Admin',
            'message': 'Hi admin here\nHope you are doing well\nI\'m here to assist you\nPlease go forward with the query',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_id': 'admin',
            'is_admin': True
        }
        
        print(f'📨 Sending admin welcome message to room {room_id}')
        emit('receive_message', admin_message, room=room_id)
        
    else:
        # Add to waiting list
        waiting_users.append(user_id)
        emit('waiting_for_partner', room=user_id)
        print(f'⏳ {username} added to waiting list (total waiting: {len(waiting_users)})')

@socketio.on('send_message')
def on_send_message(data):
    user_id = request.sid
    if user_id not in active_users or not active_users[user_id].get('room'):
        print(f'❌ Message rejected: User {user_id[:8]} not in active chat')
        return
    
    room_id = active_users[user_id]['room']
    message = data.get('message', '').strip()
    username = active_users[user_id]['username']
    
    if message:
        message_data = {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_id': user_id
        }
        
        # Send to all users in room
        emit('receive_message', message_data, room=room_id)
        print(f'💬 [{room_id}] {username}: {message[:50]}{"..." if len(message) > 50 else ""}')

@socketio.on('typing')
def on_typing(data):
    user_id = request.sid
    if user_id not in active_users or not active_users[user_id].get('room'):
        return
    
    room_id = active_users[user_id]['room']
    username = active_users[user_id]['username']
    
    # Send typing indicator to other users in room
    emit('user_typing', {
        'username': username,
        'typing': data.get('typing', False)
    }, room=room_id, include_self=False)

@socketio.on('end_chat')
def on_end_chat():
    user_id = request.sid
    if user_id not in active_users or not active_users[user_id].get('room'):
        return
    
    room_id = active_users[user_id]['room']
    username = active_users[user_id]['username']
    
    print(f'🔚 {username} ended chat in room {room_id}')
    
    # Notify other users in room
    emit('chat_ended', room=room_id, include_self=False)
    
    # Clean up room
    if room_id in active_rooms:
        for uid in active_rooms[room_id]:
            if uid in active_users:
                active_users[uid]['room'] = None
                leave_room(room_id, uid)
        del active_rooms[room_id]

if __name__ == '__main__':
    print("🚀 Starting Chat Server...")
    socketio.run(app, host='localhost', port=8000)