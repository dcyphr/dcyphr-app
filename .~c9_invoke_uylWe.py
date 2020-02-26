import os
import re

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date, datetime

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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL(os.environ['postgres://hwicvwhg:4zzgStNJkiEy3hC3gtFHrdlyLFR_vQUN@rajje.db.elephantsql.com:5432/hwicvwhg?sslmode=require'])

# This allows the user to browse the different articles
# Displays articles by recency of completion and displays only the article title and author as a link to the page that contains the actual summary
@app.route("/browse", methods=["GET", "POST"])
def browse():
    # Selects doi so we know where to route people when they click on the article link
    destination = db.execute("SELECT doi FROM summary WHERE summary.done = CAST(1 AS BIT)")
    # Creates an array of links to route people to that corresponds to what people click on
    links = []
    for i in range(len(destination)):
        links.append("read/{0}".format(destination[i]["doi"]))
    # Displays preview information about articles
    summaries = db.execute(
        "SELECT article, username, users.id FROM summary JOIN users ON summary.user_id = users.id WHERE summary.done = CAST(1 AS BIT);")
    # Gets length because there is no len function in jinja
    length = len(summaries)
    # preview = db.execute("SELECT substr(abstract, 1, 100) FROM tasks JOIN summary ON tasks.id = summary.task_id JOIN users ON summary.user_id = users.id WHERE summary.done = CAST(1 AS BIT);")
    return render_template("browse.html", summaries=summaries, links=links, length=length)

# This route displays the summaries to the people
# Note that there is a variable in the route to specify what article they are looking at
@app.route("/read/<doi>", methods=["GET", "POST"])
def read(doi):
    if request.method == "GET":
        # Gets information about article to display
        article = db.execute("SELECT article FROM summary WHERE doi=:doi", doi=doi)[0]["article"]
        summary = db.execute(
            "SELECT summary.summary, user_id, username FROM summary JOIN users ON summary.user_id = users.id WHERE doi=:doi", doi=doi)
        comments = db.execute("SELECT * FROM comments JOIN users ON comments.user_id = users.id WHERE doi=:doi", doi=doi)
        link = db.execute("SELECT link FROM summary WHERE doi=:doi", doi=doi)[0]["link"]
        likes = db.execute("SELECT likes FROM summary WHERE doi=:doi", doi=doi)[0]["likes"]
        citation = db.execute("SELECT citation FROM summary WHERE doi=:doi", doi=doi)[0]["citation"]
        article_methods = summary[0]["methods"].lower()
        methods = db.execute("SELECT name FROM methods")
        methods_list = []
        for i in range(len(methods)):
            methods_list.append(methods[i]["name"])
        methods_used = []
        method_id = []
        for method in methods_list:
            for word in method.split():
                if word.lower() in article_methods:
                    methods_used.append(method)
                    method_id.append(db.execute("SELECT id FROM methods WHERE name=:method", method=method)[0]["id"])
        methods_used = list(dict.fromkeys(methods_used))
        method_length = len(methods_used)
        # Checks if person is logged in
        # x is a variable that disables liking when true and enables liking when false
        if len(session) == 0:
            x = "true"
            y = "true"
        else:
            y = "false"
            # Checks if person already liked the post
            liked = db.execute("SELECT likes FROM users WHERE id=:user_id", user_id=session["user_id"])[0]["likes"]
            # Checks specifically if the person has liked anything
            if liked == None:
                x = "false"
                db.execute("UPDATE users SET likes = ' ' WHERE id=:user_id", user_id=session["user_id"])
            elif doi in liked:
                x = "true"
            else:
                x = "false"
        return render_template("read.html", method_length=method_length, summary=summary, article=article, link=link, likes=likes, x=x, y=y, comments=comments, citation=citation, methods_used=methods_used, method_id=method_id)
    else:
        # Handles the liking and disliking action
        dislike = request.form.get("dislike")
        like = request.form.get("like")
        likes = db.execute("SELECT likes FROM users WHERE id=:user_id", user_id=session["user_id"])[0]["likes"]
        likes = likes + " " + doi + " "
        if like:
            db.execute("UPDATE users SET likes = :likes WHERE id=:user_id", likes=likes, user_id=session["user_id"])
        if dislike == "dislike":
            db.execute("UPDATE summary SET likes = likes - 1 WHERE doi=:doi", doi=doi)
        elif like == "like":
            db.execute("UPDATE summary SET likes = likes + 1 WHERE doi=:doi", doi=doi)
        else:
        # Handles comments
            comment = request.form.get('text')
            if not comment:
                return render_template("apology.html", message="Error, please input text for your post")
            today = date.today()
            today = today.strftime("%B %d, %Y")
            db.execute("INSERT INTO comments (user_id, doi, comment, date) VALUES (:user_id, :doi, :comment, :date)",
                        user_id=session["user_id"], doi=doi, comment=comment, date=today)
        return redirect("/read/{0}".format(doi))

# Displays to the user a list of tasks that they can click on
@app.route("/tasks")
@login_required
def tasks():
    # Gets tasks that are not marked as done and orders it by request amount
    tasks = db.execute("SELECT article, doi FROM summary WHERE done = CAST(0 AS BIT) ORDER BY requests")
    length = len(tasks)
    return render_template("tasks.html", tasks=tasks, length=length)

# Allows the user to summarize a text
# You get to this route by clicking on a summary type task
@app.route("/summary/<doi>", methods=["GET", "POST"])
@login_required
def summarize(doi):
    if request.method == "GET":
        # provides contributor with information about the article they are summarizing
        article = db.execute("SELECT article FROM summary WHERE doi=:doi", doi=doi)[0]["article"]
        link = db.execute("SELECT link FROM summary WHERE doi=:doi", doi=doi)[0]["link"]
        return render_template("edit.html", article=article, link=link)
    else:
        # inserts user summary from form into summary table
        summary = request.form.get("summary")
        user = db.execute("SELECT user_id FROM summary WHERE doi=:doi", doi=doi)[0]["user_id"]
        db.execute("UPDATE summary SET summary=:summary, done=CAST(1 AS BIT) WHERE doi=:doi;",
                   summary=summary, doi=doi)
        if not user:
            db.execute("UPDATE summary SET user_id=:user_id WHERE doi=:doi;",
                   user_id=session["user_id"], doi=doi)
        return redirect("/")

# Allows user to request an article to be summarized
@app.route("/request", methods=["GET", "POST"])
def requesting():
    if request.method == "GET":
        return render_template("request.html")
    else:
        article = request.form.get("article")
        doi = request.form.get("doi")
        doi = doi.strip()
        link = request.form.get("link")
        citation = request.form.get("citation")
        # checks if PMID/DOI is already in the requested list
        if len(db.execute("SELECT doi FROM summary WHERE doi=:doi", doi=doi)) > 0:
            test = db.execute("SELECT article FROM summary WHERE doi=:doi", doi=doi)
            # checks if your PMID/DOI has the correct title if it is already in database
            if article != test[0]["article"]:
                return render_template("apology.html", message="Error, PMID already exists in database: incorrect PMID or title")
            # if already in database, it increases the number of requests by 1
            requests = db.execute("SELECT requests FROM summary WHERE doi=:doi", doi=doi)[0]["requests"] + 1
            db.execute("UPDATE summary SET requests=:requests WHERE doi=:doi", doi=doi, requests=requests)
        else:
            # if it isn't in the database, it adds it as a new task
            db.execute("INSERT INTO summary (requests, article, doi, done, link, citation) VALUES (1, :article, :doi, CAST(0 AS BIT), :link, :citation);",
                       article=article, doi=doi, link=link, citation=citation)
        return redirect("/")

# homepage with a search bar
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # db.execute("CREATE TABLE IF NOT EXISTS summary (id SERIAL PRIMARY KEY, user_id INTEGER, citation TEXT, doi TEXT, background TEXT, aims TEXT, methods TEXT, results TEXT, conclusion TEXT, task_id INTEGER, done BIT, reviewed INTEGER, remove BIT, likes INTEGER, reviewer_1 INTEGER, reviewer_2 INTEGER, FOREIGN KEY(doi) REFERENCES tasks(doi), FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY(task_id) REFERENCES tasks(id));")
        # db.execute("CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, type TEXT, citation TEXT, requests INTEGER, article TEXT, doi TEXT, done INTEGER, user_id INTEGER, link TEXT, FOREIGN KEY(user_id) REFERENCES users(id));")
        # db.execute("CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, user_id INTEGER, doi INTEGER, comment TEXT, date DATE);")
        return render_template("index.html")
    else:
        # search bar
        search = request.form.get("search")
        # gets info on things that have the searched thing in it
        results = db.execute("SELECT summary.doi, username, article, users.id FROM summary JOIN users ON summary.user_id = users.id WHERE (article LIKE :search OR summary.doi LIKE :search OR username LIKE :search OR summary.summary LIKE :search OR summary.citation LIKE :search) AND summary.done = 1", search="%" + search + "%")
        # preview = db.execute("SELECT substr(abstract, 1, 100) FROM summary JOIN tasks ON summary.doi = tasks.doi JOIN users ON summary.user_id = users.id WHERE (article LIKE :search OR summary.doi LIKE :search OR username LIKE :search OR background LIKE :search OR aims LIKE :search OR methods LIKE :search OR results LIKE :search OR conclusion LIKE :search OR summary.citation LIKE :search OR summary.abstract LIKE :search) AND summary.done = 1", search="%" + search + "%")
        # creates list of links/routes to display to user so they can click on the result and it takes them to the correct read subroute
        links = []
        length = len(results)
        for i in range(length):
            links.append("read/{0}".format(results[i]["doi"]))
        return render_template("results.html", results=results, links=links, length=length, preview=preview, search=search)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("apology.html", message="must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("apology.html", message="must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("apology.html", message="invalid username/password combination")

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
    # gets list of articles that the user has written
    articles = db.execute(
        "SELECT article, doi FROM summary WHERE user_id=:user_id AND done=CAST(1 AS BIT)", user_id=user_id)
    # gets number of articles they have written
    length = len(articles)
    # progress bar based on how much the user has summarized
    progress = round(length/60 * 100)
    # gets their username
    info = db.execute("SELECT username FROM users WHERE id=:user_id", user_id=session["user_id"])
    return render_template("profile.html", info=info, articles=articles, length=length, progress=progress)

# same as profile route but without the change password and progress bar
# public profile
@app.route("/public/<int:user_id>")
def public(user_id):
    articles = db.execute(
        "SELECT article, doi FROM summary WHERE user_id=:user_id AND done = CAST(1 AS BIT)", user_id=user_id)
    length = len(articles)
    info = db.execute("SELECT username FROM users WHERE id=:user_id", user_id=user_id)
    return render_template("public.html", articles=articles, info=info, length=length)



@app.route("/method/<int:method_id>")
def methods(method_id):
    if method_id == 0:
        methods = db.execute("SELECT name, id FROM methods")
        preview = db.execute("SELECT substr(description, 1, 100) FROM methods")
        length = len(methods)
        return render_template("methods.html", methods=methods, preview=preview, length=length)
    else:
        methods = db.execute("SELECT name, description FROM methods WHERE id=:method_id", method_id=method_id)
        return render_template("method_summary.html", methods=methods)

# route to change password
@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "GET":
        return render_template("password.html")
    else:
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        if password != confirm:
            return render_template("apology.html", message="Your passwords do not match")
        else:
            hashed = generate_password_hash(password)
            db.execute("UPDATE users SET hash = :hashed WHERE id=:user_id", hashed=hashed, user_id=session["user_id"])
        return render_template("index.html")

# allows user registration
@app.route("/register", methods=["GET", "POST"])
def register():
    # db.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT, hash TEXT, summarized INTEGER, reviewed INTEGER, likes TEXT, email TEXT)")
    if request.method == "GET":
        return render_template("register.html")
    else:
        # gets form inputs
        emailConfirmed = False
        username = request.form.get("username")
        email = request.form.get("email")
        if not email:
            return render_template("apology.html", message="You must enter an email")
        if not username:
            return render_template("apology.html", message="You must enter a username")
        if len(db.execute("SELECT id FROM users WHERE email = :email", email=email)) > 0:
            return render_template("apology.html", message="That email is already registered")
        # checks that it is a valid email
        if not re.match(r"^[A-Za-z0-9\.\+_-]+@yale.edu", email):
            return render_template("apology.html", message="Not a valid email address")
        # checks if username is taken
        if len(db.execute("SELECT id FROM users WHERE username = :username", username=username)) > 0:
            return render_template("apology.html", message="That username is taken")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if not password:
            return render_template("apology.html", message="You must enter a password")
        if password != confirm:
            return render_template("apology.html", message="Your passwords do not match")
        else:
            # generates hash of password which is stored in database
            hashed = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash, email) VALUES (:username, :hashed, :email)", username=username, hashed=hashed, email=email)
            return redirect("/login")

# displays search results
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