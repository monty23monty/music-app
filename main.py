from flask import Flask, render_template, request, redirect, url_for, flash, session
import hashlib
from hashlib import sha256
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SECRET_KEY'] = 'vT1$n&8iD4gY7oR2cVbN9LmK3jX6zQ5wM0hA8sE4fB7pZ2xW6uJ1'
db.init_app(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(120))

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = password

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    if 'logged_in' in session and session['logged_in']:
        # User is logged in
        username = session['username']
        # ... your code for logged-in users
    else:
        redirect(url_for("login"))

@app.route("/users/create", methods=["GET", "POST"])
def user_create():
    if request.method == "POST":
        password=request.form["password"].encode('utf-8')
        password = sha256(password).hexdigest()
        user = User(
            username=request.form["username"],
            email=request.form["email"],
            password=password
        )
        with open("output.txt", "wb") as f:
            f.write(request.form["username"].encode('utf-8'))
            f.write(request.form["email"].encode('utf-8'))
            f.write(request.form["password"].encode('utf-8'))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("user/create.html")

@app.route("/user/<int:id>")
def user_detail(id):
    user = User.query.get(id)
    return render_template("user/detail.html", user=user)

@app.route("/users")
def auth():
    return render_template("signUp.html")

@app.route("/login", methods = ["GET", "POST"])
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
                flash('Login successful!')
            else:
                flash('Incorrect password!')
        else:
            # User not found, display flash message
            flash('Username not found!')

    return render_template('login.html')


if __name__ == '__main__':
    app.run()