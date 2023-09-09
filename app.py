from flask import Flask, render_template, request, redirect, url_for, flash, session
from hashlib import sha256
import hashlib
from flask_sqlalchemy import SQLAlchemy
import random
import string
from flask_socketio import SocketIO, emit, join_room
from difflib import SequenceMatcher
import sqlite3 as sql
from random import randint
import eventlet


db = SQLAlchemy()
app = Flask(__name__)
socketio = SocketIO(app)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config["SECRET_KEY"] = "vT1$n&8iD4gY7oR2cVbN9LmK3jX6zQ5wM0hA8sE4fB7pZ2xW6uJ1"
db.init_app(app)
    

# Import the association table
users_rooms = db.Table('users_rooms',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('room_id', db.Integer, db.ForeignKey('room.id'))
)


class Songs(db.Model):
    id = db.Column(db.integer, primary_key=True)
    name = db.Column(db.String(80))
    month = db.Column(db.String(5))
    position = db.Column(db.Integer)
    artist = db.Column(db.String(80))


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    code = db.Column(db.String(10), unique=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    creator = db.relationship("User", backref=db.backref("created_rooms", lazy=True))
    connected_users = db.relationship('User', secondary=users_rooms, backref=db.backref('connected_rooms', lazy=True))

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
    
    rooms = db.relationship('Room', secondary=users_rooms, back_populates='connected_users', overlaps='connected_rooms')


    def __repr__(self):
        return "<User %r>" % self.username

class Game:
    def __init__(self, *players):
        # Starts a game when a Game object is created

        # Generates 15 randoms songs
        self.songs = set()
        for i in range(15):
            self.songs.add(get_random_song())

        # Stores a list of players in a dictionary containing the player name and a list of songs to be completed
        self.players = dict()
        for i in players:
            self.players[i] = self.songs.copy()
            self.giveSong(i)
   
    def giveSong(self, player):
        if len(self.players[player]):
            # Removes a random song from a players remaining set of songs
            song = self.players[player].pop()
            self.players[player]
            emit('givesong', {'song': song})

        else:
            pass # to do: Tell the player they won, tell other players they lost.

    def CheckAnswer(self, player, answer, songname):
        # Player gives us their username, answer, and name of song they were trying to guess
        if SequenceMatcher(None, answer, songname).ratio() >= 0.8:
            # to do: Tell player they were correct
            self.giveSong(player)

def get_random_song(lowerDate, upperDate, minimumPosition):
    songs = Songs.query.filter(Songs.Month.between(lowerDate, upperDate), Songs.Position >= minimumPosition).all()
    if songs:
        return songs[randint(0, len(songs) - 1)]
    return None

with app.app_context():
    db.create_all()

# ... [Rest of the code remains unchanged]


#
#
#

# Auth Code


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for("login"))

    created_rooms = user.created_rooms if user.created_rooms else []
    rooms = Room.query.all()
    return render_template(
        "home.html", username=user.username, created_rooms=created_rooms, rooms=rooms
    )


@app.route("/users/create", methods=["GET", "POST"])
def user_create():
    if request.method == "POST":
        if request.method == "POST":
            username = request.form["username"]
            email = request.form["email"]
            password = request.form["password"]
            code = generate_random_code()

            existing_user = User.query.filter(
                db.or_(User.username == username, User.email == email)
            ).first()

            if existing_user:
                if existing_user.username == username:
                    flash("Username already exists.")
                if existing_user.email == email:
                    flash("Email already exists.")

                return redirect(url_for("auth"))
            else:
                # Create a new user
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                new_user = User(
                    username=username, email=email, password=hashed_password, code=code
                )
                db.session.add(new_user)
                db.session.commit()
                flash("User successfully registered!")
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
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user:
            # User exists, check the password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if user.password == hashed_password:
                # Password is correct, proceed with login process
                session["logged_in"] = True
                session["username"] = user.username
                session["user_id"] = user.id  # Add this line to set the user_id
                flash("Login successful!")
                return redirect(url_for("home"))
            else:
                flash("Incorrect password!")
        else:
            # User not found, display flash message
            flash("Username not found!")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()  # Clear the user session data
    flash("You have been logged out successfully.")
    return redirect(url_for("login"))


#
#
#
#

# room code


def generate_random_code(length=6):
    characters = string.digits
    code = "".join(random.choice(characters) for _ in range(length))
    return code


@app.route("/room/<code>")
def room_detail(code):
    if "user_id" not in session:
        return redirect(url_for("login"))
    room = Room.query.filter_by(code=code).first()
    user_id = session["user_id"]
    user = User.query.get(user_id)
    if not room:
        flash("Room not found.")
        return redirect(url_for("home"))

    return render_template("room/detail.html", room=room, username=user.username)

@app.route("/room/<code>/play")
def StartGame(code):
    if "user_id" not in session:
        return redirect(url_for("login"))
    room = Room.query.filter_by(code=code).first()
    user_id = session["user_id"]
    if user_id != room.creator_id:
        flash("You are not the host")
        return redirect(url_for(f"room/{code}"))
    game = Game(*room.connected_users)
    



@app.route("/room")
def room():
    return render_template("room/join.html")




@socketio.on("join_room")
def handle_join_room(data):
    print("Received join_room event with data:", data)
    room_id = data["room_id"]
    user_id = session["user_id"]

    print(f"Received join_room event. room_id: {room_id}, user_id: {user_id}")

    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if room and user:
        if user not in room.connected_users:
            room.connected_users.append(user)
            db.session.commit()

        # Instead of room.get_connected_users(), use room.connected_users directly
        connected_users = [u.username for u in room.connected_users]
        print(f"Emitting connected_users_update event. users: {connected_users}")
        join_room(room_id)
        socketio.emit(
            "connected_users_update", {"users": connected_users}, room=room_id

        )




@app.route("/rooms/create", methods=["GET", "POST"])
def room_create():
    if request.method == "POST":
        name = request.form["name"]
        code = generate_random_code()  # Implement a function to generate a unique code

        # Create a new room
        new_room = Room(name=name, code=code, creator_id=session["user_id"])
        db.session.add(new_room)
        db.session.commit()

        # Update the user's code with the room code
        user = User.query.get(session["user_id"])
        user.code = code
        db.session.commit()

        # Emit an event to all connected clients to update the room list
        socketio.emit(
            "room_created", {"room_code": new_room.code, "room_name": new_room.name}
        )

        flash("Room created successfully!")
        return redirect(url_for("room_detail", code=new_room.code))

    user = User.query.get(session["user_id"])

    return render_template("room/create.html", username=user.username)


@app.route("/join", methods=["POST"])
def join_room_route():
    # Get room_id from the form data
    room_id = request.form.get("room_id")

    # Get user_id from the session
    user_id = session.get("user_id")

    if not room_id or not user_id:
        flash("An error occurred. Please try again.")
        return redirect(url_for("home"))

    # Get the room and the user from the database
    room = Room.query.get(room_id)
    user = User.query.get(user_id)

    if not room or not user:
        flash("An error occurred. Please try again.")
        return redirect(url_for("home"))

    # Add the user to the room's connected_users
    if user not in room.connected_users:
        room.connected_users.append(user)
        db.session.commit()

        # Emit a connected_users_update event to update the user list in real time
        socketio.emit(
            "connected_users_update",
            {"users": room.get_connected_users()},
            room=room_id,
        )

    # Redirect the user to the room detail view
    return redirect(url_for("room_detail", id=room_id))


@app.route("/leave/<int:room_id>", methods=["GET"])
def leave_room(room_id):

    # Get user_id from the session
    user_id = session.get("user_id")

    if not room_id or not user_id:
        flash("An error occurred. Please try again.")
        return redirect(url_for("home"))

    # Get the room and the user from the database
    room = Room.query.get(room_id)
    user = User.query.get(user_id)
    print(room)
    print(user)

    if not room or not user:
        flash("An error occurred. Please try again.")
        return redirect(url_for("home"))

    # Remove the user from the room's connected_users
    if user in room.connected_users:
        room.connected_users.remove(user)
        db.session.commit()
        print("Removing User")

        # Emit a connected_users_update event to update the user list in real time
        print("Emitting event for room:", room_id)
        socketio.emit(
            "connected_users_update",
            {"users": room.get_connected_users()},
            room=room_id,
        )

    # Redirect the user to the home view
    return redirect(url_for("home"))


if __name__ == "__main__":
    eventlet.wsgi.server(eventlet.listen(("192.168.86.228", 5000)), app)
    socketio.run(app)
