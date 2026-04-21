from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'besiktas_feda_1903'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
db = SQLAlchemy(app)

# Video gönderimi için buffer boyutunu 100MB'a çıkardık
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=100 * 1024 * 1024)

online_users = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(500), default="https://api.dicebear.com/7.x/bottts/svg?seed=default")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(50))
    avatar = db.Column(db.String(500))
    content = db.Column(db.Text)
    caption = db.Column(db.Text)
    msg_type = db.Column(db.String(10)) 
    reply_to = db.Column(db.Text) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/manifest.webmanifest')
def manifest():
    return send_from_directory('static', 'manifest.webmanifest', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def service_worker():
    response = send_from_directory('static', 'service-worker.js', mimetype='application/javascript')
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/api/notification-icon')
def notification_icon():
    return jsonify({
        "icon": url_for('static', filename='icons/icon-192.svg', _external=True)
    })

@app.route('/')
def index():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if not user: return redirect(url_for('logout'))
        limit = datetime.utcnow() - timedelta(days=14)
        Message.query.filter(Message.timestamp < limit).delete()
        db.session.commit()
        old_messages = Message.query.order_by(Message.timestamp.asc()).all()
        return render_template('index.html', user=user, old_messages=old_messages)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        avatar_url = request.form.get('avatar_url') or f"https://api.dicebear.com/7.x/bottts/svg?seed={username}"
        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password, password):
                session['username'] = username
                session.permanent = True
                return redirect(url_for('index'))
            return "Hatalı şifre!"
        else:
            new_user = User(username=username, password=generate_password_hash(password), avatar=avatar_url)
            db.session.add(new_user)
            db.session.commit()
            session['username'] = username
            session.permanent = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    new_username = request.form.get('username', '').strip().lower()
    new_password = request.form.get('password')
    new_avatar = request.form.get('avatar_url')
    if new_username and new_username != user.username:
        if not User.query.filter_by(username=new_username).first():
            user.username = new_username
            session['username'] = new_username
    if new_password: user.password = generate_password_hash(new_password)
    if new_avatar: user.avatar = new_avatar
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user:
            online_users[user.username] = {"avatar": user.avatar, "name": user.username.capitalize()}
            emit('update_users', online_users, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        online_users.pop(session['username'], None)
        emit('update_users', online_users, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    emit('display_typing', {'user': session.get('username', '').capitalize(), 'status': data['status']}, broadcast=True, include_self=False)

@socketio.on('message')
def handle_message(data):
    user = User.query.filter_by(username=session.get('username')).first()
    if user:
        new_msg = Message(
            user=user.username.capitalize(),
            avatar=user.avatar,
            content=data['content'],
            caption=data.get('caption', ''),
            msg_type=data.get('type', 'text'),
            reply_to=data.get('reply_to')
        )
        db.session.add(new_msg)
        db.session.commit()
        emit('message', {
            'id': new_msg.id, 'user': new_msg.user, 'content': new_msg.content,
            'caption': new_msg.caption, 'avatar': new_msg.avatar, 
            'type': new_msg.msg_type, 'reply_to': new_msg.reply_to
        }, broadcast=True)

@socketio.on('edit_message')
def handle_edit(data):
    msg = Message.query.get(data['id'])
    if msg and msg.user.lower() == session.get('username').lower():
        msg.content = data['content']
        db.session.commit()
        emit('message_edited', {'id': data['id'], 'content': data['content']}, broadcast=True)

@socketio.on('delete_message')
def handle_delete(data):
    msg = Message.query.get(data['id'])
    if msg and msg.user.lower() == session.get('username').lower():
        db.session.delete(msg)
        db.session.commit()
        emit('message_deleted', {'id': data['id']}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port)
