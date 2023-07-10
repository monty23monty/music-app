from flask import Flask, render_template, request, redirect, url_for, flash, session
import hashlib
from hashlib import sha256
from flask_sqlalchemy import SQLAlchemy
import random
import string
from flask_socketio import SocketIO, emit

db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SECRET_KEY'] = 'vT1$n&8iD4gY7oR2cVbN9LmK3jX6zQ5wM0hA8sE4fB7pZ2xW6uJ1'
db.init_app(app)


# Import the association table
users_rooms = db.Table('users_rooms',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('room_id', db.Integer, db.ForeignKey('room.id'), primary_key=True)
)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    code = db.Column(db.String(10), unique=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    creator = db.relationship('User', backref=db.backref('created_rooms', lazy=True))
    connected_users = db.relationship('User', secondary=users_rooms, backref=db.backref('rooms', lazy=True))



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(120))
    code = db.Column(db.String(10), nullable=True)

    def __init__(self, username, email, password, code):
        self.username = username
        self.email = email
        self.password = password
        self.code = code

    def __repr__(self):
        return '<User %r>' % self.username



with app.app_context():
    db.create_all()

#
#
#

#Auth Code

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('login'))

    created_rooms = user.created_rooms if user.created_rooms else []
    return render_template('home.html', username=user.username, created_rooms=created_rooms)



@app.route("/users/create", methods=["GET", "POST"])
def user_create():
    if request.method == "POST":
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            code = generate_random_code()

            existing_user = User.query.filter(db.or_(User.username == username, User.email == email)).first()

            if existing_user:
                if existing_user.username == username:
                    flash('Username already exists.')
                if existing_user.email == email:
                    flash('Email already exists.')

                return redirect(url_for("auth"))
            else:
                # Create a new user
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                new_user = User(username=username, email=email, password=hashed_password, code=code)
                db.session.add(new_user)
                db.session.commit()
                flash('User successfully registered!')
                return redirect(url_for("login"))

    return render_template("user/create.html")

@app.route("/user/<int:id>")
def user_detail(id):
    user = User.query.get(id)
    return render_template("user/detail.html", user=user)

@app.route("/users")
def auth():
    return render_template("signUp.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user:
            # User exists, check the password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if user.password == hashed_password:
                # Password is correct, proceed with login process
                session['logged_in'] = True
                session['username'] = user.username
                session['user_id'] = user.id  # Add this line to set the user_id
                flash('Login successful!')
                return redirect(url_for("home"))
            else:
                flash('Incorrect password!')
        else:
            # User not found, display flash message
            flash('Username not found!')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()  # Clear the user session data
    flash('You have been logged out successfully.')
    return redirect(url_for('login'))

#
#
#
#

#room code

def generate_random_code(length=6):
    characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
    code = ''.join(random.choice(characters) for _ in range(length))
    return code


@app.route("/rooms/create", methods=["GET", "POST"])
def room_create():
    if request.method == "POST":
        name = request.form['name']
        code = generate_random_code()  # Implement a function to generate a unique code

        # Create a new room
        new_room = Room(name=name, code=code, creator_id=session['user_id'])
        db.session.add(new_room)
        db.session.commit()

        # Update the user's code with the room code
        user = User.query.get(session['user_id'])
        user.code = code
        db.session.commit()

        flash('Room created successfully!')
        return redirect(url_for("room_detail", id=new_room.id))

    return render_template("room/create.html")


@app.route("/room/<int:id>")
def room_detail(id):
    room = Room.query.get(id)
    
    # Check if the user's code matches the room's code
    user = User.query.get(session['user_id'])
    if room.code != user.code:
        flash('Invalid room code!')
        return redirect(url_for("home"))

    # Add the user to the connected users of the room
    room.connected_users.append(user)
    db.session.commit()

    return render_template("room/detail.html", room=room)


@app.route('/room/<int:room_id>/join', methods=['POST'])
def join_room(room_id):
    room = Room.query.get(room_id)
    user = User.query.get(session['user_id'])

    if room and user:
        room.connected_users.append(user)
        db.session.commit()
        flash('You have joined the room!', 'success')
    else:
        flash('Failed to join the room.', 'error')

    return redirect(url_for('room_detail', id=room_id))

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room_id']
    user_id = data['user_id']

    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if room and user:
        room.connected_users.append(user)
        db.session.commit()

        # Emit the updated list of connected users to all clients in the room
        emit('connected_users_update', {'users': room.get_connected_users()}, room=room_id)


if __name__ == '__main__':
    app.run()