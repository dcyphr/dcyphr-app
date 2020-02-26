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
    destination = db.execute("SELECT doi FROM summary WHERE summary.reviewed = 3")
    links = []
    for i in range(len(destination)):
        links.append("read/{0}".format(destination[i]["doi"]))
    summaries = db.execute("SELECT article, username FROM tasks JOIN summary ON tasks.id = summary.task_id JOIN users ON summary.user_id = users.id WHERE summary.reviewed = 3;")
    length = len(summaries)
    return render_template("browse.html", summaries=summaries, links=links, length=length)

@app.route("/read/<doi>")
def read(doi):
    article = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)[0]["article"]
    summary = db.execute("SELECT summary FROM summary WHERE doi=:doi", doi=doi)
    link = db.execute("SELECT link FROM tasks WHERE doi=:doi", doi=doi)[0]["link"]
    return render_template("read.html", summary=summary, article=article, link=link)

# Displays to the user a list of tasks that they can click on
@app.route("/tasks")
@login_required
def tasks():
    tasks = db.execute("SELECT type, article, doi FROM tasks WHERE (type ='review') OR (type='summary' AND done=0) ORDER BY requests")
    length = len(tasks)
    return render_template("tasks.html", tasks=tasks, length=length)

# Allows the user to summarize a text
# You get to this route by clicking on a summary type task
@app.route("/summary/<doi>", methods=["GET", "POST"])
@login_required
def summarize(doi):
    if request.method == "GET":
        article = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)[0]["article"]
        link = db.execute("SELECT link FROM tasks WHERE doi=:doi", doi=doi)[0]["link"]
        return render_template("summarize.html", article=article, link = link)
    else:
        summary = request.form.get("summary")
        task_id = db.execute("SELECT id FROM tasks WHERE doi=:doi", doi=doi)[0]["id"]
        requests = db.execute("SELECT requests FROM tasks WHERE doi=:doi", doi=doi)[0]["requests"]
        article = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)[0]["article"]
        if not task_id:
            return render_template("apology.html", message="No valid DOI was entered")
        db.execute("INSERT INTO summary (user_id, doi, summary, task_id, done, reviewed) VALUES (:user_id, :doi, :summary, :task_id, 1, 0);", user_id=session["user_id"], doi=doi, summary=summary, task_id=task_id)
        db.execute("UPDATE tasks SET done=1 WHERE doi=:doi;", doi=doi)
        db.execute("INSERT INTO tasks (type, requests, article, doi, done, user_id) VALUES ('review', :requests, :article, :doi, 0, :user_id);", requests=requests, article=article, doi=doi, user_id=session["user_id"])
        return redirect("/")

# Allows user to review a summary
# You get to this route by clicking on a review type task
@app.route("/review/<doi>", methods=["GET", "POST"])
@login_required
def review(doi):
    if request.method == "POST":
        passed = request.form.get("review")
        user_id = session["user_id"]
        reviewers = (db.execute("SELECT reviewer_1, reviewer_2, reviewer_3 FROM summary WHERE doi=:doi", doi=doi))[0]
        if user_id in reviewers:
            return render_template("apology.html", message="You have already reviewed this article")
        elif reviewers["reviewer_1"] == "NULL":
            db.execute("UPDATE summary SET reviewer_1 = :user_id WHERE doi = :doi", user_id=user_id, doi=doi)
        elif reviewers["reviewer_2"] == "NULL":
            db.execute("UPDATE summary SET reviewer_2 = :user_id WHERE doi = :doi", user_id=user_id, doi=doi)
        if passed == "yes":
            db.execute("UPDATE tasks SET done = done + 1 WHERE doi=:doi", doi=doi)
            db.execute("UPDATE summary SET reviewed = reviewed + 1 WHERE doi=:doi", doi=doi)
            if db.execute("SELECT done FROM tasks WHERE doi=:doi AND type='review'", doi=doi)[0]["done"] == 3:
                db.execute("DELETE FROM tasks WHERE doi=:doi AND type='review'", doi=doi)
        else:
            db.execute("DELETE FROM summary WHERE doi=:doi", doi=doi)
            db.execute("DELETE FROM tasks WHERE doi=:doi AND type='review'", doi=doi)
            db.execute("UPDATE tasks SET done=0 WHERE doi=:doi AND type='summary'", doi=doi)
        return redirect("/")
    else:
        article = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)[0]["article"]
        summary = db.execute("SELECT summary FROM summary WHERE doi=:doi", doi=doi)
        link = db.execute("SELECT link FROM tasks WHERE doi=:doi", doi=doi)[0]["link"]
        return render_template("review.html", summary=summary, link=link, article=article)

# Allows user to request an article to be summarized
@app.route("/request", methods=["GET", "POST"])
def requesting():
    if request.method == "GET":
        return render_template("request.html")
    else:
        article = request.form.get("article")
        doi = request.form.get("doi")
        link = request.form.get("link")
        if len(db.execute("SELECT doi FROM tasks WHERE doi=:doi", doi=doi)) > 0:
            test = db.execute("SELECT article FROM tasks WHERE doi=:doi", doi=doi)
            if article != test[0]["article"]:
                return render_template("apology.html", message="DOI already exists in database: incorrect DOI or title")
            requests = db.execute("SELECT requests FROM tasks WHERE doi=:doi", doi=doi)[0]["requests"] + 1
            db.execute("UPDATE tasks SET requests=:requests WHERE doi=:doi", doi=doi, requests=requests)
        else:
            db.execute("INSERT INTO tasks (type, requests, article, doi, done, link) VALUES ('summary', 1, :article, :doi, 0, :link);", article=article, doi=doi, link=link)
        return redirect("/")

# homepage with a search bar
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        db.execute("CREATE TABLE IF NOT EXISTS 'summary' (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, doi TEXT, summary TEXT, task_id INTEGER, done BIT, reviewed INTEGER, remove BIT, FOREIGN KEY(doi) REFERENCES tasks(doi), FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY(task_id) REFERENCES tasks(id));")
        db.execute("CREATE TABLE IF NOT EXISTS 'tasks' (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, requests INTEGER, article TEXT, doi TEXT, done INTEGER, user_id INTEGER, link TEXT, FOREIGN KEY(user_id) REFERENCES users(id));")
        return render_template("index.html")
    else:
        search = request.form.get("search")
        results = db.execute("SELECT summary.doi, username, article FROM summary JOIN tasks ON summary.doi = tasks.doi JOIN users ON summary.user_id = users.id WHERE article LIKE :search", search= "%" + search + "%")
        links=[]
        length=len(results)
        for i in range(length):
            links.append("read/{0}".format(results[i]["doi"]))
        return render_template("results.html", results=results, links=links, length=length)

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

@app.route("/profile/<int:user_id>", methods=["GET", "POST"])
@login_required
def profile(user_id):
    if request.method == "GET":
        articles = db.execute("SELECT article, summary.doi FROM summary JOIN tasks ON summary.doi = tasks.doi WHERE summary.user_id = :user_id", user_id = user_id)
        length = len(articles)
        info = db.execute("SELECT username FROM users WHERE id=:user_id", user_id=session["user_id"])
        return render_template("profile.html", info=info, articles=articles, length=length)
    else:
        info = db.execute("SELECT username FROM users WHERE id=:user_id", user_id=session["user_id"])
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        if password != confirm:
            return render_template("apology.html", message="Your passwords do not match")
        else:
            hashed = generate_password_hash(password)
            db.execute("UPDATE users SET hash = :hashed WHERE id=:user_id", hashed=hashed, user_id=user_id)
        return render_template("profile.html", info=info)

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

@app.route("/results")
def results():
    return render_template("results.html")


@app.route("/about")
def about():
    return render_template("about.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)