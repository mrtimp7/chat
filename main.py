from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
socketio = SocketIO(app, cors_allowed_origins="*")

# Modeller
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
    msg_type = db.Column(db.String(10), default='text')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return redirect(url_for('logout'))
        
        # 14 günlük temizlik
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
    
    new_username = request.form.get('username').strip().lower()
    new_password = request.form.get('password')
    new_avatar = request.form.get('avatar_url')

    if new_username and new_username != user.username:
        if not User.query.filter_by(username=new_username).first():
            user.username = new_username
            session['username'] = new_username
    if new_password:
        user.password = generate_password_hash(new_password)
    if new_avatar:
        user.avatar = new_avatar
        
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('message')
def handleMessage(data):
    user_name = session.get('username')
    if user_name:
        user = User.query.filter_by(username=user_name).first()
        if user:
            new_msg = Message(
                user=user.username.capitalize(), 
                avatar=user.avatar, 
                content=data['content'], 
                msg_type=data.get('type', 'text')
            )
            db.session.add(new_msg)
            db.session.commit()
            emit('message', {
                'user': new_msg.user, 
                'content': new_msg.content, 
                'avatar': new_msg.avatar, 
                'type': new_msg.msg_type
            }, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port)
