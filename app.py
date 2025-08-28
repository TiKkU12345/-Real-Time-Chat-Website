from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
from datetime import datetime
import socket

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active users and their rooms
active_users = {}
waiting_users = []
active_rooms = {}

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return '127.0.0.1'

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f'User {request.sid} connected')

@socketio.on('disconnect')
def on_disconnect():
    user_id = request.sid
    print(f'User {user_id} disconnected')
    
    # Remove from waiting list
    if user_id in waiting_users:
        waiting_users.remove(user_id)
    
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
        
        del active_users[user_id]

@socketio.on('find_chat')
def on_find_chat(data):
    user_id = request.sid
    username = data.get('username', f'User_{user_id[:8]}')
    
    active_users[user_id] = {
        'username': username,
        'room': None
    }
    
    if len(waiting_users) > 0:
        # Match with waiting user
        other_user = waiting_users.pop(0)
        room_id = str(uuid.uuid4())
        
        # Add both users to room
        join_room(room_id, user_id)
        join_room(room_id, other_user)
        
        # Update user info
        active_users[user_id]['room'] = room_id
        active_users[other_user]['room'] = room_id
        
        # Track room
        active_rooms[room_id] = [user_id, other_user]
        
        # Notify both users
        emit('chat_found', {
            'room_id': room_id,
            'partner': active_users[other_user]['username']
        }, room=user_id)
        
        emit('chat_found', {
            'room_id': room_id,
            'partner': active_users[user_id]['username']
        }, room=other_user)
        
        # 🎯 ADD ADMIN WELCOME MESSAGE HERE
        admin_message = {
            'username': 'Admin',
            'message': 'Hi admin here\nHope you are doing well\nI\'m here to assist you\nPlease go forward with the query',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_id': 'admin',
            'is_admin': True
        }
        
        # Send admin message to both users in the room
        emit('receive_message', admin_message, room=room_id)
        
        print(f'Matched {user_id} with {other_user} in room {room_id}')
        print(f'Admin welcome message sent to room {room_id}')
    else:
        # Add to waiting list
        waiting_users.append(user_id)
        emit('waiting_for_partner', room=user_id)
        print(f'User {user_id} added to waiting list')

@socketio.on('send_message')
def on_send_message(data):
    user_id = request.sid
    if user_id not in active_users or not active_users[user_id].get('room'):
        return
    
    room_id = active_users[user_id]['room']
    message = data.get('message', '')
    username = active_users[user_id]['username']
    
    if message.strip():
        message_data = {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_id': user_id
        }
        
        # Send to all users in room
        emit('receive_message', message_data, room=room_id)
        print(f'Message from {username} in room {room_id}: {message}')

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
    
    # Notify other users in room
    emit('chat_ended', room=room_id, include_self=False)
    
    # Clean up room
    if room_id in active_rooms:
        for uid in active_rooms[room_id]:
            if uid in active_users:
                active_users[uid]['room'] = None
                leave_room(room_id, uid)
        del active_rooms[room_id]
    
    print(f'Chat ended in room {room_id}')

if __name__ == '__main__':
    print("🚀 Starting Chat Server...")
    print("✅ Admin welcome message enabled!")
    
    # Get the local IP address dynamically
    local_ip = get_local_ip()
    print(f"🌐 Server starting on {local_ip}:5000")
    print(f"🔗 Access your chat at: http://{local_ip}:5000")
    print(f"🏠 Local access: http://localhost:5000")
    
    # Use 0.0.0.0 to bind to all interfaces (most flexible)
    # This allows access from both localhost and your network IP
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)