from flask import Flask, render_template, request, redirect, url_for, flash, session
import hashlib
from hashlib import sha256
from flask_sqlalchemy import SQLAlchemy
import random
import string
import eventlet
import eventlet.wsgi
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from flask_migrate import Migrate




db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SECRET_KEY'] = 'vT1$n&8iD4gY7oR2cVbN9LmK3jX6zQ5wM0hA8sE4fB7pZ2xW6uJ1'
db.init_app(app)
socketio = SocketIO(app)


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

    def get_connected_users(self):
        return [user.username for user in self.connected_users]

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

migrate = Migrate(app, db)

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
    rooms = Room.query.all()
    return render_template('home.html', username=user.username, created_rooms=created_rooms, rooms=rooms)


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


@app.route("/room/<int:id>")
def room_detail(id):
    room = Room.query.get(id)
    if not room:
        flash('Room not found.')
        return redirect(url_for("home"))

    return render_template("room/detail.html", room=room)

@socketio.on('join_room')
def handle_join_room(data):
    print('Received join_room event with data:', data)
    room_id = data['room_id']
    user_id = session['user_id']

    print(f'Received join_room event. room_id: {room_id}, user_id: {user_id}')  # Added for debugging

    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if room and user:
        if user not in room.connected_users:
            room.connected_users.append(user)
            db.session.commit()

        connected_users = room.get_connected_users()
        print(f'Emitting connected_users_update event. users: {connected_users}')  # Added for debugging
        # Make the user join the room in the SocketIO sense.
        join_room(room_id)

        # Emit the update only to users in this room.
        socketio.emit('connected_users_update', {'users': room.get_connected_users()}, room=room_id)

def ack():
    print('message was received!')


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

        # Emit an event to all connected clients to update the room list
        socketio.emit('room_created', {'room_id': new_room.id, 'room_name': new_room.name})


        flash('Room created successfully!')
        return redirect(url_for("room_detail", id=new_room.id))

    return render_template("room/create.html")

@app.route("/join", methods=["POST"])
def join_room_route():
    # Get room_id from the form data
    room_id = request.form.get('room_id')

    # Get user_id from the session
    user_id = session.get('user_id')

    if not room_id or not user_id:
        flash('An error occurred. Please try again.')
        return redirect(url_for('home'))

    # Get the room and the user from the database
    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if not room or not user:
        flash('An error occurred. Please try again.')
        return redirect(url_for('home'))

    # Add the user to the room's connected_users
    if user not in room.connected_users:
        room.connected_users.append(user)
        db.session.commit()

        # Emit a connected_users_update event to update the user list in real time
        socketio.emit('connected_users_update', {'users': room.get_connected_users()}, room=room_id)

    # Redirect the user to the room detail view
    return redirect(url_for('room_detail', id=room_id))


@app.route("/leave", methods=["POST"])
def leave_room():
    # Get room_id from the form data
    room_id = request.form.get('room_id')

    # Get user_id from the session
    user_id = session.get('user_id')

    if not room_id or not user_id:
        flash('An error occurred. Please try again.')
        return redirect(url_for('home'))

    # Get the room and the user from the database
    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if not room or not user:
        flash('An error occurred. Please try again.')
        return redirect(url_for('home'))

    # Remove the user from the room's connected_users
    if user in room.connected_users:
        room.connected_users.remove(user)
        db.session.commit()

        # Emit a connected_users_update event to update the user list in real time
        socketio.emit('connected_users_update', {'users': room.get_connected_users()}, room=room_id)

    # Redirect the user to the home view
    return redirect(url_for('home'))




if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('127.0.0.1', 5000)), app)
    socketio.run(app)