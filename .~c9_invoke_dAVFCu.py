import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///nvision.db")

# This allows the user to browse the different articles
# Displays articles by recency of completion and displays only the article title and author as a link to the page that contains the actual summary
@app.route("/browse", methods=["GET", "POST"])
def browse():
    summaries = db.execute("SELECT article, users.username FROM tasks JOIN summary ON tasks.id = summary.task_id JOIN users ON summary.user_id = users.id WHERE summary IS NOT NULL")
    return render_template("browse.html", summaries=summaries)

# Displays to the user a list of tasks that they can click on
@app.route("/tasks")
@login_required
def tasks():
    tasks = db.execute("SELECT type, article, doi FROM tasks WHERE done=0 ORDER BY requests")
    length = len(tasks)
    return render_template("tasks.html", tasks=tasks, length=length)

# Allows the user to summarize a text
# You get to this route by clicking on a summary type task
@app.route("/summary", methods=["GET", "POST"])
@login_required
def summarize():
    if request.method == "GET":
        return render_template("summarize.html")
    else:
        summary = request.form.get("summary")
        doi = request.form.get("doi")
        task_id = db.execute("SELECT id FROM tasks WHERE doi=:doi", doi=doi)[0]["id"]
        requests = db.execute("SELECT requests FROM tasks WHERE doi=:doi", doi=doi)[0]["requests"]
        article = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)[0]["article"]
        if not task_id:
            return render_template("apology.html", message="No valid DOI was entered")
        db.execute("INSERT INTO summary (user_id, doi, summary, task_id) VALUES (:user_id, :doi, :summary, :task_id);", user_id=session["user_id"], doi=doi, summary=summary, task_id=task_id)
        db.execute("UPDATE tasks SET done=1 WHERE doi=:doi;", doi=doi)
        for i in range(3):
            db.execute("INSERT INTO tasks (type, requests, article, doi, done) VALUES ('review', :requests, :article, :doi, 0);", requests=requests, article=article, doi=doi)
        return redirect("/")

# Allows user to review a summary
# You get to this route by clicking on a review type task
@app.route("/review", methods=["GET", "POST"])
@login_required
def review():
    return render_template("apology.html")

# Allows user to request an article to be summarized
@app.route("/request", methods=["GET", "POST"])
def requesting():
    if request.method == "GET":
        return render_template("request.html")
    else:
        article = request.form.get("article")
        doi = request.form.get("doi")
        if doi in db.execute("SELECT doi FROM tasks;"):
            requests = db.execute("SELECT requests FROM tasks WHERE doi=:doi", doi=doi)[0]["requests"] + 1
            db.execute("UPDATE tasks SET requests=:requests WHERE doi=:doi", doi=doi, requests=requests)
        else:
            db.execute("INSERT INTO tasks (type, requests, article, doi, done) VALUES ('summary', 1, :article, :doi, 0);", article=article, doi=doi)
        return redirect("/")

# homepage with a search bar
@app.route("/")
def index():
    db.execute("CREATE TABLE IF NOT EXISTS 'summary' (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, doi TEXT, summary TEXT, task_id INTEGER, FOREIGN KEY(doi) REFERENCES tasks(doi), FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY(task_id) REFERENCES tasks(id));")
    db.execute("CREATE TABLE IF NOT EXISTS 'tasks' (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, requests INTEGER, article TEXT, doi TEXT, done BIT, user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id));")
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    db.execute("CREATE TABLE IF NOT EXISTS 'users' ('id' INTEGER PRIMARY KEY AUTOINCREMENT, 'username' TEXT, 'hash' TEXT, 'summarized' INTEGER, 'reviewed' INTEGER)")
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        if not username:
            return render_template("apology.html", message="You must enter a username")
        if username in db.execute("SELECT username FROM users"):
            return render_template("apology.html", message="That username is taken")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if not password:
            return render_template("apology.html", message="You must enter a password")
        if password != confirm:
            return render_template("apology.html", message="Your passwords do not match")
        else:
            hashed = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashed)", username=username, hashed=hashed)
            return redirect("/login")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)