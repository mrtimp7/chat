from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'besiktas_feda_1903'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Veritabanı Modeli
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(500), default="https://api.dicebear.com/7.x/bottts/svg?seed=default")

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        return render_template('index.html', user=user)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        avatar_url = request.form.get('avatar_url').strip()
        
        if not avatar_url:
            avatar_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={username}"
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            if check_password_hash(user.password, password):
                session['username'] = username
                session.permanent = True
                return redirect(url_for('index'))
            return "Hatalı şifre! Tekrar dene."
        else:
            new_user = User(username=username, password=generate_password_hash(password), avatar=avatar_url)
            db.session.add(new_user)
            db.session.commit()
            session['username'] = username
            session.permanent = True
            return redirect(url_for('index'))
            
    return render_template('login.html')

@socketio.on('message')
def handleMessage(data):
    user = User.query.filter_by(username=session.get('username')).first()
    if user:
        emit('message', {
            'user': user.username.capitalize(),
            'msg': data['msg'],
            'avatar': user.avatar
        }, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port)
