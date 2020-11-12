import os
import re
import math
import sendgrid
import datetime

from oauthlib.oauth2 import WebApplicationClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date, datetime
from bs4 import BeautifulSoup
import jellyfish
from helpers import apology, login_required, readability, remove_scripts, percent_remove, summry, get_apa, generate_confirmation_token, confirm_token, remove_html_tags
from itsdangerous import URLSafeTimedSerializer

import requests
import random
import json

# Configure application
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev')

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


# db = SQL("sqlite:///dcyphr.db")
db = SQL(os.environ['DATABASE_URL'])

# Google authentication
GOOGLE_CLIENT_ID = "809605574601-dcuiplqktluk68ih4p61jstg2g44n1ld.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'dev')
FACEBOOK_APP_ID = "569416280425492"
FACEBOOK_CLIENT_SECRET = os.environ.get('FACEBOOK_CLIENT_SECRET', 'dev')

GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

client = WebApplicationClient(GOOGLE_CLIENT_ID)
def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# add description to glossary of terms
@app.route("/addmethod", methods=["POST"])
def addmethod():
    title = request.form.get("title")
    description = request.form.get("description")
    db.execute("INSERT INTO methods (name, description) VALUES (:title, :description)", title=title, description=description) # inserts a term title and description into the database
    return redirect("/method/0")

# explore page with tag clusters
@app.route("/explore")
def explore():
    tags = db.execute("SELECT title, text, tags.link, tags.id, COUNT(tag_id) AS count FROM tags LEFT JOIN tagitem ON tags.id=tag_id GROUP BY tags.id, tags.title, tags.text, tags.link;") # selects relevant tag information
    method_length = db.execute("SELECT COUNT(*) AS count FROM methods")[0]['count']
    return render_template("explore.html", tags=tags, method_length=method_length)


# allows users to browse summaries
@app.route("/browse/<int:page>", methods=["GET", "POST"])
def browse(page):
    if request.method == "GET":
        # sets how many articles per page
        page_length = 10

        # gets summary information for articles to show
        summaries = db.execute(
            "SELECT summary_date, summary.likes, article, first, last, users.id AS user, doi, summary.id, summary.summary FROM summary JOIN users ON summary.user_id = users.id WHERE summary.done = CAST(1 AS BIT) and summary.approved = 1 ORDER BY summary.likes DESC LIMIT :limit OFFSET :offset;", limit=page_length, offset=page_length*page)
        
        # edge case handling
        length = db.execute("SELECT COUNT(*) AS count FROM summary WHERE done=CAST(1 AS BIT) AND approved=1")[0]['count']
        if length == 0:
            p = "No summaries to show. Please contribute."
            return render_template("browse.html", summaries=summaries, length=length, p=p)
        elif length <= 10:
            x = False
        else:
            x = True
        number = int(math.ceil(length/page_length))

        # gets summary information from database that are done and approved
        if page + 1 == number:
            page_length = len(summaries)

        # gets tag information
        tags = db.execute("SELECT id, title FROM tags")
        tags_length = len(tags)

        # gets preview for summaries
        soup = []
        for i in range(len(summaries)):
            soup.append(percent_remove(str(BeautifulSoup(summaries[i]["summary"], features = "html5lib").get_text()[0:500])))
        return render_template("browse.html", tags=tags, tags_length=tags_length, summaries=summaries, length=length, preview=soup, page=page, page_length = page_length, number=number, x=x)

# shows edit history of a particular summary
@app.route("/history/<int:summary_id>", methods=["GET", "POST"])
def history(summary_id):
    if request.method == "GET":
        info = db.execute("SELECT * FROM history JOIN users ON users.id = history.user_id WHERE summary_id=:summary_id", summary_id=summary_id) # gets version history information
        article = db.execute("SELECT article, link, citation, doi, id FROM summary WHERE id=:summary_id", summary_id=summary_id) # gets relevant article information
        length=len(info)
        # checks if user is logged in and if user is admin
        if len(session) == 0:
            y = 0
        else:
            y = db.execute("SELECT admin FROM users WHERE id=:user_id", user_id=session["user_id"])[0]['admin']
        if y == 0:
            x = False
        else:
            x = True
        return render_template("history.html", info=info, length=length, article=article, summary_id=summary_id, x=x)
    else:
        # handles deleting version
        try:
            delete=request.form.get("delete")
            db.execute("DELETE FROM history WHERE version=:version AND summary_id=:summary_id", version=delete, summary_id=summary_id)
            return redirect("/history/{}".format(summary_id))
        except:
            # handles reverting summary to previous version
            version = request.form.get("version")
            summary=db.execute("SELECT text FROM history WHERE version=:version AND summary_id=:summary_id", version=version, summary_id=summary_id)[0]['text']
            max_version=db.execute("SELECT MAX(version) AS max_version FROM history WHERE summary_id=:summary_id", summary_id=summary_id)[0]['max_version']
            db.execute("UPDATE summary SET summary=:summary WHERE id=:summary_id", summary=summary, summary_id=summary_id)
            # creates new edit history that indicates the reverting action
            db.execute("INSERT INTO history (version, date, user_id, text, summary_id) VALUES (:version, :date, :user_id, :text, :summary_id)", version=max_version + 1, date=date.today(), user_id=session['user_id'], text="Reverted back to <a href='/version/{0}/{1}'>version {1}</a>".format(summary_id, version), summary_id=summary_id)
            return redirect("/history/{}".format(summary_id))

# shows the information for a particular edit version of a summary
@app.route("/version/<int:summary_id>/<int:version>", methods=["GET", "POST"])
def version(summary_id, version):
    if request.method == "GET":
        info = db.execute(
            "SELECT * FROM history JOIN users ON users.id=history.user_id JOIN summary ON summary_id=summary.id WHERE summary_id=:summary_id AND version=:version", summary_id=summary_id, version=version
            )[0] # shows version history
        return render_template("version.html", info=info, summary_id=summary_id)

# shows reported issues of a summary
@app.route("/issues/<int:summary_id>", methods=["GET", "POST"])
def issues(summary_id):
    if request.method == "GET":
        article = db.execute("SELECT article, link, citation, doi, id FROM summary WHERE id=:summary_id", summary_id=summary_id)
        info = db.execute("SELECT *, issues.id AS id FROM issues JOIN users ON users.id = asker_id WHERE summary_id=:summary_id", summary_id=summary_id)
        length = len(info)
        # checks if user is logged in
        if len(session) == 0:
            x = False
        else:
            x = True
        # checks if a particular issue is marked as resolved
        y=[]
        for i in range(length):
            if info[i]['resolved'] == 1:
                y.append(True)
            else:
                y.append(False)
        return render_template("issues.html", info=info, length=length, article=article, x=x, y=y, summary_id=summary_id)
    else:
        # gets new user it was assigned to
        new_assignee=request.form.get("new_assignee")
        # gets resolved information
        checked=request.form.get("checked")
        unchecked=request.form.get("unchecked")
        # sees if the action was to resolve or unresolve
        if checked:
            db.execute("UPDATE issues SET resolved=0 WHERE id=:issue_id", issue_id=checked)
        elif unchecked:
            db.execute("UPDATE issues SET resolved=1 WHERE id=:issue_id", issue_id=unchecked)
        # sees if the action was to assign a new user
        elif new_assignee:
            db.execute("UPDATE issues SET assignee=:new_assignee WHERE id=:issue_id", new_assignee=new_assignee, issue_id=request.form['assignee_button'])
        # sees if action was to add a new issue
        else:
            issue=request.form.get("text")
            assignee=request.form.get("assignee")
            if not assignee:
                assignee = ""
            today=date.today()
            db.execute("INSERT INTO issues (summary_id, asker_id, assignee, text, date) VALUES (:summary_id, :asker_id, :assignee, :text, :timestamp)", summary_id=summary_id, asker_id=session["user_id"], assignee=assignee, timestamp=today, text=issue)
        return redirect("/issues/{}".format(summary_id))



@app.route("/_endorse/<int:summary_id>", methods=["GET"])
@login_required
def endorse(summary_id):
    user_id = session['user_id']
    check = db.execute("SELECT id FROM endorsements WHERE user_id=:user_id AND summary_id=:summary_id", user_id=user_id, summary_id=summary_id)

    if len(check) == 0:
        db.execute("INSERT INTO endorsements (user_id, summary_id) VALUES (:user_id, :summary_id)", user_id=user_id, summary_id=summary_id)
        info = db.execute("SELECT first, last, bio FROM users WHERE id=:user_id", user_id=user_id)[0]
    else:
        info = None
    return jsonify(info)

@app.route("/_dislikes/<int:summary_id>", methods=["GET"])
def dislikes(summary_id):
    today = date.today()
    today = today.strftime("%B %d, %Y")
    liked = db.execute("SELECT vote FROM likes WHERE user_id=:user_id AND summary_id=:summary_id", user_id=session["user_id"], summary_id=summary_id)
    if liked != []:
        liked = liked[0]["vote"]
    if liked != []:
        db.execute("UPDATE likes SET vote = 0 WHERE user_id=:user_id AND summary_id=:summary_id", user_id=session["user_id"], summary_id=summary_id)
    else:
        db.execute("INSERT INTO likes (user_id, summary_id, vote, date) VALUES (:user_id, :summary_id, -1, :date)",
                    user_id=session["user_id"], summary_id=summary_id, date=today)
    db.execute("UPDATE users SET points = points - 1 WHERE id=:user_id", user_id=session["user_id"])
    likes = db.execute("SELECT COALESCE(SUM(vote)) AS sum FROM likes WHERE summary_id=:summary_id", summary_id=summary_id)[0]["sum"]
    db.execute("UPDATE summary SET likes=:likes WHERE id=:summary_id",likes=likes,summary_id=summary_id)
    return jsonify(likes)


@app.route("/_likes/<int:summary_id>", methods=["GET"])
def likes(summary_id):
    today = date.today()
    today = today.strftime("%B %d, %Y")
    liked = db.execute("SELECT vote FROM likes WHERE user_id=:user_id AND summary_id=:summary_id", user_id=session["user_id"], summary_id=summary_id)
    if liked != []:
        liked = liked[0]["vote"]
    if liked != []:
        db.execute("UPDATE likes SET vote = 1 WHERE user_id=:user_id AND summary_id=:summary_id", user_id=session["user_id"], summary_id=summary_id)
    else:
        db.execute("INSERT INTO likes (user_id, summary_id, vote, date) VALUES (:user_id, :summary_id, 1, :date)",
                    user_id=session["user_id"], summary_id=summary_id, date=today)
    db.execute("UPDATE users SET points = points + 1 WHERE id=:user_id", user_id=session["user_id"])
    likes = db.execute("SELECT COALESCE(SUM(vote), 0) AS sum FROM likes WHERE summary_id=:summary_id", summary_id=summary_id)[0]["sum"]
    db.execute("UPDATE summary SET likes=:likes WHERE id=:summary_id",likes=likes,summary_id=summary_id)

    return jsonify(likes)

@app.route("/_delete/<int:summary_id>", methods=["GET"])
def delete(summary_id):
    delete = request.args.get("tag_id")
    db.execute("DELETE FROM tagitem WHERE tag_id=:tag_id AND item_id=:item_id", tag_id=delete, item_id=summary_id)
    return jsonify(delete)

@app.route("/_add/<int:summary_id>", methods=["GET"])
def add(summary_id):
    tag = request.args.get("tag", type=str)

    summary_tags = db.execute("SELECT title FROM tags JOIN tagitem ON tags.id=tagitem.tag_id WHERE tagitem.item_id=:summary_id", summary_id=summary_id)
    tags = db.execute("SELECT title FROM tags")

    if any(d.get('title') == tag for d in summary_tags):
        return None
    elif any(d.get('title') == tag for d in tags):
        tag_id = db.execute("SELECT id FROM tags WHERE title=:tag", tag=tag)[0]['id']
    else:
        db.execute("INSERT INTO tags (title) VALUES (:tag)", tag=tag)
        tag_id = db.execute("SELECT id FROM tags WHERE title=:tag", tag=tag)[0]['id']
    db.execute("INSERT INTO tagitem (item_id, tag_id) VALUES (:summary_id, :tag_id);", summary_id=summary_id, tag_id=tag_id)
    return jsonify({'tag_name': tag, 'tag_id': tag_id})

@app.route("/flag/<int:summary_id>", methods=["POST"])
def flag(summary_id):
    user = db.execute("SELECT user_id FROM summary WHERE id=:summary_id", summary_id=summary_id)[0]["user_id"]
    db.execute("UPDATE summary SET approved=0 WHERE id=:summary_id", summary_id=summary_id)
    db.execute("UPDATE users SET points = points - 20 WHERE id=:user_id", user_id=user)
    return redirect("/")

@app.route("/comments/<int:summary_id>", methods=["POST"])
def comments(summary_id):
    comment = request.form.get('comment')
    reply = request.form.get('reply')
    today = date.today()
    today = today.strftime("%B %d, %Y")
    # Comment
    if not reply:
        db.execute("INSERT INTO comments (user_id, summary_id, comment, date, likes, reply) VALUES (:user_id, :summary_id, :comment, :date, :likes, :reply)",
                    user_id=session["user_id"], summary_id=summary_id, comment=comment, date=today, likes=0, reply=0)
        comment_id = db.execute("SELECT id FROM comments WHERE summary_id=:summary_id AND comment=:comment ORDER BY id DESC LIMIT 1", summary_id=summary_id, comment=comment)[0]["id"]
        db.execute("UPDATE comments SET comment_id=:comment_id WHERE summary_id=:summary_id AND comment=:comment ORDER BY id DESC LIMIT 1", comment_id=comment_id, summary_id=summary_id, comment=comment)
    # Reply
    else:
        comment_id = request.form.get('comment_button')
        db.execute("UPDATE comments SET last=0 WHERE (summary_id=:summary_id) AND (comment_id=:comment_id) AND last=1", summary_id=summary_id, comment_id=comment_id)
        db.execute("INSERT INTO comments (user_id, summary_id, comment, date, likes, reply, comment_id, last) VALUES (:user_id, :summary_id, :comment, :date, :likes, :reply, :comment_id, :last)",
                    user_id=session["user_id"], summary_id=summary_id, comment=reply, date=today, likes=0, reply=1, comment_id=comment_id, last=1)
    return redirect("/read/{0}".format(summary_id))


# This route displays the summaries to the people
# Note that there is a variable in the route to specify what article they are looking at
@app.route("/read/<int:summary_id>", methods=["GET", "POST"])
def read(summary_id):
    if request.method == "GET":
        # Gets information about article to display

        summary = db.execute(
            "SELECT summary_date, summary.id, summary.summary, link, article, citation, coffee, user_id, doi, first, last, bio, verified FROM summary JOIN users ON summary.user_id = users.id WHERE summary.id=:summary_id", summary_id=summary_id)
        comments = db.execute("SELECT * FROM comments JOIN users ON comments.user_id = users.id WHERE summary_id=:summary_id ORDER BY comment_id, comments.id", summary_id=summary_id)

        endorsements = db.execute("SELECT user_id, verified, first, last, bio FROM endorsements JOIN users ON user_id=users.id WHERE summary_id=:summary_id", summary_id=summary_id)
        likes = db.execute("SELECT COALESCE(SUM(vote), 0) AS sum FROM likes WHERE summary_id=:summary_id", summary_id=summary_id)[0]["sum"]

        tags = db.execute("SELECT title, tags.id FROM tags JOIN tagitem ON tags.id=tagitem.tag_id WHERE tagitem.item_id=:summary_id", summary_id=summary_id)
        tag_length = len(tags)
        all_tags = db.execute("SELECT title FROM tags")
        all_tags_len = len(all_tags)

        # gets top contributors
        contributors = db.execute("SELECT first, last, user_id, verified, bio, COUNT(*) AS count FROM history JOIN users ON user_id=users.id WHERE summary_id=:summary_id GROUP BY user_id, first, last, verified, bio ORDER BY COUNT(*) DESC LIMIT 3", summary_id=summary_id)
        c_length = len(contributors)

        # handles display of the html
        html = summary[0]['summary']
        soup = BeautifulSoup(html, features="html5lib")
        title_list=[]
        for title in soup.find_all("h2"):
            title_list.append(title.text.strip())
            title["id"] = title.text.strip()
        title_length=len(title_list)
        summary_actual=soup

        # Checks if person is logged in
        # can_like is a variable that disables liking when true and enables liking when false
        # logged_out checks if person is logged out
        # is_admin checks if person is admin
        is_admin = "false"
        if len(session) == 0:
            can_like = "true"
            logged_out = "true"
        else:
            logged_out = "false"
            if db.execute("SELECT admin FROM users WHERE id=:user_id", user_id=session['user_id'])[0]['admin'] == 1:
                is_admin = "true"
            # Checks if person already liked the post
            liked = db.execute("SELECT vote FROM likes WHERE user_id=:user_id AND summary_id=:summary_id", user_id=session["user_id"], summary_id=summary_id)
            if liked == []:
                can_like = "false"
            elif liked[0]["vote"] == 1:
                can_like = "enable-dislike"
            else:
                can_like = "enable-like"
        return render_template("read.html", coffee=summary[0]['coffee'], endorsements=endorsements, contributors=contributors, c_length=c_length, is_admin=is_admin, all_tags=all_tags, all_tags_len=all_tags_len, tag_length=tag_length, tags=tags, summary_actual=percent_remove(str(summary_actual)), title_length=title_length, titles=title_list, summary_id=summary_id, summary=summary, likes=likes, can_like=can_like, logged_out=logged_out, comments=comments)


# gives browse page for a specific tag
@app.route("/tag/<int:tag_id>/<int:page>", methods=["GET", "POST"])
def tag(tag_id, page):
    if request.method == "GET":
        page_length = 10

        titles = db.execute("SELECT summary_date, article, summary.id AS summary_id, summary.likes, first, last, users.id, summary.summary FROM users JOIN summary ON summary.user_id=users.id JOIN tagitem on summary.id=tagitem.item_id WHERE tagitem.tag_id=:tag_id AND summary.approved=1 AND summary.done = CAST(1 AS BIT) ORDER BY summary.likes DESC LIMIT :limit OFFSET :offset;", limit=page_length, offset=page_length*page, tag_id=tag_id)

        plength = db.execute("SELECT COUNT(*) AS count FROM tagitem JOIN summary on summary.id=item_id WHERE summary.done = CAST(1 AS BIT) AND summary.approved = 1 AND tag_id=:tag_id", tag_id=tag_id)[0]['count']

        number = int(math.ceil(plength/page_length))
        if plength <= 10:
            x=True
        else:
            x=False

        if page + 1 == number:
            page_length = len(titles)
        length= len(titles)
        tags = db.execute("SELECT id, title, text FROM tags WHERE id=:tag_id", tag_id=tag_id)
        tags_length = len(tags)
        if len(session) == 0:
            admin = 0
        else:
            admin = db.execute("SELECT admin FROM users WHERE id=:user_id", user_id=session['user_id'])[0]['admin']
        # handles case where there are no summaries in that tag
        if length == 0:
            p = "No summaries to show. Please contribute."
            return render_template("tag.html", titles=titles, tags=tags, tags_length=tags_length, length=length, x=x, p=p, admin=admin, tag_id=tag_id, number=number, page=page)
        else:
            soup = []
            for i in range(length):
                soup.append(percent_remove(str(BeautifulSoup(titles[i]["summary"], features = "html5lib").get_text()[0:500])))
            return render_template("tag.html", tags=tags, tags_length=tags_length, admin=admin, titles=titles, length=length, preview=soup, page=page, page_length=page_length, tag_id=tag_id, number=number)
    else:
        desc = request.form.get("description")
        db.execute("UPDATE tags SET text = :desc WHERE id=:tag_id", desc=desc, tag_id=tag_id)
        return redirect("/tag/{}/0".format(tag_id))
        
# page where admins input information for QuickTasks
@app.route("/adminsuggestions", methods=["GET", "POST"])
@login_required
def adminsuggestions():
    if request.method =="GET":
        return render_template("adminsugg.html")
    else:
        title = request.form.get("title")
        doi = request.form.get("doi")
        text = request.form.get("text")
        api_length = int(len(text.split(".")) * 0.6)
        # API call for extracting key sentences
        try:
            suggestion = summry(text, api_length)['sm_api_content']
        except:
            return redirect("/adminsuggestions")
        # need to add second level of NLP processing here
        summary_id = db.execute("SELECT id FROM summary WHERE doi=:doi", doi=doi)[0]['id']
        db.execute("INSERT INTO suggestions (title, display, suggestion, summary_id) VALUES (:title, :display, :suggestion, :summary_id)", title=title, display=text, summary_id=summary_id, suggestion=suggestion)
        return render_template("adminsugg.html")

# page for QuickTasks for contributors
@app.route("/suggestions/<int:sugg_id>", methods=["GET", "POST"])
@login_required
def suggestions(sugg_id):
    if request.method == "GET":
        count = db.execute("SELECT COUNT(*) AS count FROM suggestions")[0]['count']
        # checks if there are suggestions left
        if count == 0:
            return render_template("suggestions.html", p=True)
        # takes you to the first suggestion if the input suggestion id does not exist
        if sugg_id == 0:
            var1 = db.execute("SELECT id FROM suggestions LIMIT 1")[0]['id']
            return redirect("/suggestions/{0}".format(var1))
        # takes you to the suggestion id that you input
        else:
            info = db.execute("SELECT * FROM suggestions WHERE id=:sugg_id", sugg_id=sugg_id)[0]
            summary_info = db.execute("SELECT article, link FROM summary WHERE id=:summary_id", summary_id=info["summary_id"])[0]
            return render_template("suggestions.html", info=info, summary_info=summary_info)
    else:
        # handles approvals
        if not request.form.get("next"):
            info = db.execute("SELECT * FROM suggestions WHERE id=:sugg_id", sugg_id=sugg_id)[0]
            text = request.form.get("summary")
            # creates text to append to the summary
            new = "<h2>" + info["title"] + "</h2>" + "<p>" + text + "</p>"
            db.execute("UPDATE summary SET summary = summary || :new, done=CAST(1 AS BIT), approved=0 WHERE id=:summary_id", new=new, summary_id=info["summary_id"])
            db.execute("DELETE FROM suggestions WHERE id=:sugg_id", sugg_id=info['id'])
            # goes to the next suggestion
            next_value = db.execute("SELECT id FROM suggestions LIMIT 1")
            return redirect("/suggestions/{0}".format(next_value[0]['id']))
        else:
            # goes to the next suggestion
            next_value = db.execute("SELECT id FROM suggestions WHERE id > :sugg_id LIMIT 1", sugg_id=sugg_id)
            if not next_value:
                return render_template("suggestions.html", q=True)
            return redirect("/suggestions/{0}".format(next_value[0]['id']))

# handles editing of the citation
@app.route("/apa/<int:summary_id>", methods=["GET", "POST"])
@login_required
def apa(summary_id):
    if request.method == "GET":
        info = db.execute("SELECT article, citation, link FROM summary WHERE id=:summary_id", summary_id=summary_id)[0]
        length = len(info)
        return render_template("apa.html", info=info, length=length)
    else:
        citation = request.form.get("citation")
        db.execute("UPDATE summary SET citation=:citation WHERE id=:summary_id", citation=citation, summary_id=summary_id)
        return redirect("/read/{0}".format(summary_id))

# handles editing of the doi
@app.route("/doi/<int:summary_id>", methods=["GET", "POST"])
@login_required
def doi(summary_id):
    if request.method == "GET":
        info = db.execute("SELECT article, doi, link FROM summary WHERE id=:summary_id", summary_id=summary_id)[0]
        length = len(info)
        return render_template("doi.html", info=info, length=length)
    else:
        doi = request.form.get("doi")
        db.execute("UPDATE summary SET doi=:doi WHERE id=:summary_id", summary_id=summary_id, doi=doi)
        return redirect("/")

# Displays to the user a list of tasks that they can click on
@app.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():
    if request.method == "GET":
        # Gets tasks that are not marked as done and orders it by request amount
        tasks = db.execute("SELECT article, doi, summary.id, request_date, first, last, users.id AS user_id FROM summary LEFT JOIN users ON users.id=request_user WHERE done = CAST(0 AS BIT) AND bookmarked = 0 ORDER BY first")

        length = len(tasks)
        return render_template("tasks.html", tasks=tasks, length=length)

    else:
        user_id = session["user_id"]
        summary_id = request.form.get("bookmark")
        today = date.today()
        db.execute("UPDATE summary SET bookmarked=:user_id, bookmarked_date=:date WHERE id=:summary_id", user_id=user_id, summary_id=summary_id, date=today)

        tasks = db.execute("SELECT article, id, doi FROM summary WHERE done = CAST(0 AS BIT) AND bookmarked = :user_id ORDER BY requests DESC", user_id=user_id)
        length = len(tasks)


        #return render_template("bookmarks.html", tasks=tasks, length=length)
        return redirect("/bookmarks")


# handles bookmarks
@app.route("/bookmarks", methods=["GET", "POST"])
@login_required
def bookmarks():
    if request.method == "GET":
        user_id = session["user_id"]
        tasks = db.execute("SELECT article, id, doi FROM summary WHERE done = CAST(0 AS BIT) AND bookmarked = :user_id ORDER BY requests DESC", user_id=user_id)
        length = len(tasks)
        return render_template("bookmarks.html", tasks=tasks, length=length)

    else:
        user_id = session["user_id"]
        summary_id = request.form.get("unbookmark")
        db.execute("UPDATE summary SET bookmarked=0 WHERE id=:summary_id", summary_id=summary_id)

        tasks = db.execute("SELECT article, id, doi FROM summary WHERE done = CAST(0 AS BIT) AND bookmarked = :user_id ORDER BY requests DESC", user_id=user_id)
        length = len(tasks)
        return render_template("bookmarks.html", tasks=tasks, length=length)


@app.route("/ai/<int:summary_id>", methods=["POST"])
def ai(summary_id):
    text=request.form.get("text")
    api_length = int(len(text.split(".")) * 0.6)
    output=summry(text, api_length)
    try:
        output=output["sm_api_content"]
    except:
        output=output['sm_api_message']
    return redirect(url_for('edit', summary_id=summary_id, z=True, output=output, **request.args))

# Allows user to make edits to a task or summary
@app.route("/edit/<int:summary_id>")
@login_required
def edit(summary_id):

    # provides contributor with information about the article they are summarizing
    article = db.execute("SELECT article, user_id, link, summary FROM summary WHERE id=:summary_id", summary_id=summary_id)
    username = db.execute("SELECT username FROM users WHERE id=:user_id", user_id=article[0]["user_id"])
    return render_template("edit.html", article=article, summary=percent_remove(str(article[0]['summary'])), username=username, output="", z=False, summary_id=summary_id)

@app.route("/_submission/<int:summary_id>", methods=["POST"])
@login_required
def submission(summary_id):

    # inserts user summary from form into summary table
    summary_new_html = remove_scripts(request.form.get("summary"))

    # checks if user is primary author
    if request.form['submit_button'] == 'save':
        db.execute("UPDATE summary SET summary=:summary WHERE id=:summary_id", summary=summary_new_html, summary_id=summary_id)
        return redirect("/edit/{}".format(summary_id))
        
    user = db.execute("SELECT user_id FROM summary WHERE id=:summary_id", summary_id=summary_id)[0]["user_id"]

    if not user:
        db.execute("UPDATE summary SET summary=:summary, done=CAST(1 AS BIT), user_id=:user_id WHERE id=:summary_id;",
                user_id=session["user_id"], summary_id=summary_id, summary=summary_new_html)
    else:
        db.execute("UPDATE summary SET summary=:summary, done=CAST(1 AS BIT) WHERE id=:summary_id;",
                summary=summary_new_html, summary_id=summary_id)

    db.execute("UPDATE users SET points=points+10 WHERE id=:user_id", user_id=session['user_id'])

    # handles versioning and saving version information
    version = db.execute("SELECT COALESCE(MAX(version), -1) AS max_version FROM history WHERE summary_id=:summary_id", summary_id=summary_id)[0]['max_version'] + 1
    db.execute("INSERT INTO history (version, date, user_id, text, summary_id) VALUES (:version, :date, :user_id, :text, :summary_id)", version=version, date=date.today(), user_id=session["user_id"], text=summary_new_html, summary_id=summary_id)

    return redirect("/")
# Allows user to request an article to be summarized
@app.route("/request", methods=["GET", "POST"])
def requesting():
    if request.method == "GET":
        return render_template("request.html", message="", user=len(session))
    else:
        article = request.form.get("article")
        doi = request.form.get("doi")
        link = request.form.get("link")
        request_date = date.today()
        request_user = session["user_id"]
        try:
            citation = get_apa(doi)
        except:
            citation = "Not available. Please add it."
        # checks if PMID/DOI is already in the requested list
        if len(db.execute("SELECT doi FROM summary WHERE doi=:doi", doi=doi)) > 0:

            # if already in database, it increases the number of requests by 1
            
            db.execute("UPDATE summary SET requests=requests+1 WHERE doi=:doi", doi=doi)
        else:
            with open('templates/edit_guidelines.html', 'r') as f:
                summary = f.read()
            # if it isn't in the database, it adds it as a new task
            db.execute("INSERT INTO summary (requests, article, doi, done, link, citation, likes, approved, request_date, request_user, summary, tsv) VALUES (1, :article, :doi, CAST(0 AS BIT), :link, :citation, 0, 0, :request_date, :request_user, :summary, to_tsvector(:article));",
                       article=article, doi=doi, link=link, citation=citation, request_date=request_date, request_user=request_user, summary=summary)
        return render_template("request.html", message="Awesome! Your request has been made. &#127881;")

@app.route("/search", methods=["POST"])
def search():
    # search bar
    search = request.form.get("search").lower()
    # gets info on things that have the searched thing in it
    results = db.execute(""" 
    SELECT summary.id AS summary_id, summary_date, ts_headline(summary.summary, to_tsquery('english', :search), 'MaxFragments=5, MaxWords=20, MinWords=5') AS summary, first, last, article, users.id FROM summary JOIN users ON user_id=users.id WHERE summary.tsv @@ to_tsquery(:search) OR users.tsv_name @@ to_tsquery(:search);
    """, search=search)
    length = len(results)

    return render_template("results.html", results=results, length=length, search=search)

# homepage with a search bar
@app.route("/")
def index():
    leaderboard = db.execute("SELECT first, last, id, points FROM users WHERE points > 0 ORDER BY points DESC LIMIT 5")
    random_article = db.execute("SELECT id FROM summary WHERE done=CAST(1 AS BIT) AND approved=1 ORDER BY RANDOM() LIMIT 1")[0]['id']
    lead_length = len(leaderboard)
    return render_template("index.html", leaderboard=leaderboard, lead_length=lead_length, random_article=random_article)

#LOGIN_HERE
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        

        # Query database for username
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", incorrect=True)

        # Check to see if user has confirmed their account
        if rows[0]['confirmed'] == 0:
            session["user_id"] = rows[0]["id"]
            return redirect("/unconfirmed/{}".format(session['user_id']))
        else:
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]
            session["remember_me"] = True
            welcome = rows[0]['welcome']
            if welcome == 2:
                # Redirect user to home page
                return redirect(url_for(".profile", user_id=session['user_id'], message=True))
            else:
                return redirect(url_for(".welcome", welcome=welcome, user_id=session['user_id'], first=rows[0]['first']))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/welcome/<int:user_id>")
@login_required
def welcome(user_id):
    return render_template("welcome.html", first=request.args['first'], user_id=user_id)

@app.route("/_welcome/<int:user_id>", methods=["POST"])
@login_required
def _welcome(user_id):
    if request.form['step'] == '1':
        if not request.form['fact']:
            fact = ''
        else:
            fact = request.form['fact']
        bio = "{0} in {1} from {2} in {3}. {4} {5}".format(request.form['degree'], request.form['subject'], request.form['school'], request.form['year'], request.form['xp'], fact)
        db.execute("UPDATE users SET bio=:bio, welcome=:welcome WHERE id=:user_id", welcome=1, bio=bio, user_id=user_id)
        return {}
    else:
        db.execute("UPDATE users SET welcome=:welcome WHERE id=:user_id", welcome=2, user_id=user_id)
        return {}


#GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
#GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)


@app.route("/google-login")
def googlogin():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri=request.base_url + "/callback"
    if 'https' in redirect_uri:
        pass
    else:
        redirect_uri=redirect_uri.replace('http', 'https')
    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    print(authorization_endpoint)
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)



@app.route("/google-login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send request to get tokens! Yay tokens!
    redi=request.base_url
    if 'https' not in redi:
        redi=redi.replace('http', 'https')
    auth=request.url
    if 'https' not in auth:
        auth=auth.replace('http', 'https')
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=auth,
        redirect_url=redi,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        users_email = userinfo_response.json()["email"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    # user = User(
    #    id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    #)

    # Doesn't exist? Add to database
    #if not User.get(unique_id):
    #    User.create(unique_id, users_name, users_email, picture)

    # Begin user session by logging the user in
    #login_user(user)
    rows = db.execute("SELECT * FROM users WHERE email = :users_email",
                      users_email=users_email)

    # Ensure username exists and password is correct
    if len(rows) != 1:
        return render_template("apology.html", message="Sorry, we could not find an acccount associated with this email address")

    # Check to see if user has confirmed their account
    rows[0]['confirmed'] = 1
    session["user_id"] = rows[0]["id"]
    session["remember_me"] = True
    # Redirect user to home page
    return redirect("/")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# bio editing for the user
@app.route("/bio/<int:user_id>", methods=["GET", "POST"])
@login_required
def bio(user_id):
    if request.method == "GET":
        bio = db.execute("SELECT bio FROM users WHERE id=:user_id", user_id=user_id)[0]['bio']
        return render_template("bio.html", bio=bio)
    else:
        bio = remove_scripts(request.form.get("bio"))
        db.execute("UPDATE users SET bio=:bio WHERE id=:user_id", user_id=user_id, bio=bio)
        return redirect(url_for("profile", user_id=user_id))

# profile page for the user
@app.route("/profile/<int:user_id>", methods=["GET", "POST"])
@login_required
def profile(user_id):
    try:
        message=request.args['message']
    except:
        message=False
    # gets list of articles that the user has written
    articles = db.execute(
        "SELECT article, id, approved, pinned FROM summary WHERE user_id=:user_id AND done=CAST(1 AS BIT) ORDER BY approved DESC", user_id=user_id)
    pinned = db.execute(
        "SELECT article, id FROM summary WHERE user_id=:user_id AND pinned=1", user_id=user_id)
    # gets number of articles they have written
    length = len(articles)
    points = db.execute("SELECT points FROM users WHERE id=:user_id", user_id=session["user_id"])[0]['points']

    # gets their username
    info = db.execute("SELECT bio, username, first, last, verified, email, coffee FROM users WHERE id=:user_id", user_id=session["user_id"])
    token = generate_confirmation_token(info[0]['email'], app)

    admin = db.execute("SELECT admin FROM users WHERE id=:user_id", user_id=session["user_id"])[0]['admin']
    if info[0]['bio'] == None:
        info[0]['bio'] = "This user has no bio right now."
    if points == None:
        points = 0
    return render_template("profile.html", info=info, pinned=pinned, articles=articles, message=message, length=length, admin=admin, points=points, user_id=user_id, token=token, coffee=info[0]['coffee'])

@app.route("/_coffee/<int:user_id>", methods=["POST"])
@login_required
def coffee(user_id):
    link = request.form.get("coffeeLink")
    db.execute("UPDATE users SET coffee=:coffee WHERE id=:user_id", coffee=link, user_id=user_id)
    return redirect("/profile/{}".format(user_id))

@app.route("/_pin/<int:article_id>/<int:user_id>")
def pin(article_id, user_id):
    db.execute("UPDATE summary SET pinned=1 WHERE id=:article_id", article_id=article_id)
    return redirect("/profile/{}".format(user_id))

# public profile that other users view
@app.route("/public/<int:user_id>")
def public(user_id):
    articles = db.execute(
        "SELECT article, approved, id FROM summary WHERE user_id=:user_id AND done = CAST(1 AS BIT) ORDER BY approved DESC", user_id=user_id)
    length = len(articles)
    info = db.execute("SELECT bio, username, points, first, last, admin, verified, coffee FROM users WHERE id=:user_id", user_id=user_id)
    pinned = db.execute(
        "SELECT article, id FROM summary WHERE user_id=:user_id AND pinned=1", user_id=user_id)
    if info[0]['points'] == None:
        info[0]['points'] = 0
    if info[0]['bio'] == None:
        info[0]['bio'] = "This user has no bio right now."
    return render_template("public.html", articles=articles, info=info, length=length, coffee=info[0]['coffee'], pinned=pinned)

# laboratory methods that are hard coded into database
@app.route("/method/<int:method_id>")
def methods(method_id):
    if method_id == 0:
        methods = db.execute("SELECT name, id FROM methods")
        preview = db.execute("SELECT substr(description, 1, 400) FROM methods")
        length = len(methods)
        session_len = len(session)
        return render_template("methods.html", methods=methods, preview=preview, length=length, session_len=session_len)
    else:
        x = False
        if len(session) != 0:
            x = True
        methods = db.execute("SELECT name, description, id FROM methods WHERE id=:method_id", method_id=method_id)
        return render_template("method_summary.html", methods=methods, x=x)

@app.route("/methodupdate/<int:method_id>", methods=["POST"])
@login_required
def methodupdate(method_id):
    summary = request.form.get("summary")
    db.execute("UPDATE methods SET description = :summary WHERE id=:method_id", summary=summary, method_id=method_id)
    return redirect("/method/{}".format(method_id))

# route to change password
@app.route("/password/<password_token>", methods=["GET", "POST"])
def password(password_token):
    try:
        email = confirm_token(password_token, app)
    except:
        flash('The link is invalid or has expired.', 'danger')
    if request.method == "GET":
        return render_template("password.html")
    else:
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        if password != confirm:
            flash(u"Oops! Those don't match.", 'error')
            return redirect("/password/{}".format(password_token))
        else:
            hashed = generate_password_hash(password)
            db.execute("UPDATE users SET hash = :hashed WHERE email=:email", hashed=hashed, email=email)
        flash(u"Success! Password updated.")
        return redirect('/login')


# allows user registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        # gets form inputs
        first = request.form.get("first")
        last = request.form.get("last")
        username = request.form.get("username")
        email = request.form.get("email")
        newsletter = request.form.get("newsletter")

        if len(db.execute("SELECT id FROM users WHERE email = :email", email=email)) > 0:
            flash(u"That email is already registered.", "danger")
            return redirect('/register')
        # checks that it is a valid email
        if not re.match(r"^[A-Za-z0-9\.\+_-]+@", email):
            flash(u"Are you sure that's a real email?", "danger")
            return redirect('/register')
        # checks if username is taken
        if len(db.execute("SELECT id FROM users WHERE username = :username", username=username)) > 0:
            flash(u"Sorry, that username is taken.", "danger")
            return redirect('/register')
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if password != confirm:
            flash(u"Oops. Those passwords don't match.", "danger")
            return redirect('/register')
        else:

            hashed = generate_password_hash(password)
            if newsletter:
                db.execute("INSERT INTO users (username, hash, email, first, last, newsletter, tsv_name) VALUES (:username, :hashed, :email, :first, :last, 1, to_tsvector(CONCAT(:first, ' ', :last, ' ', :username)))", username=username, hashed=hashed, email=email, first=first, last=last)
            else:
                db.execute("INSERT INTO users (username, hash, email, first, last, newsletter, tsv_name) VALUES (:username, :hashed, :email, :first, :last, 0, to_tsvector(CONCAT(:first, ' ', :last, ' ', :username)))", username=username, hashed=hashed, email=email, first=first, last=last)
#send confirmation email
            token = generate_confirmation_token(email, app)
            
            confirm_url = url_for('confirm_email', token=token, _external=True)
            with open('templates/register_email.html', 'r') as f:
                html_string = f.read()
            message = Mail(
                from_email='team@dcyphr.org',
                to_emails=email,
                subject='Confirm your dcyphr account',
                html_content=html_string.format(first, confirm_url))
                # html_content='<h2 style="font-family: Georgia">Welcome to <span style="color: #017bff">dcyphr</span>, {0}!<p>Please follow this link to confirm that this is your email.</p><a href={1}><button class="btn btn-primary border20">Confirm account</button></a>'.format(user[0]['first'], confirm_url))
            try:
                sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY', 'dev'))
                response = sg.send(message)
                print(response.status_code)
                print(response.body)
                print(response.headers)
            except Exception as e:
                print(e)
            return redirect("/login")


@app.route("/google-register")
def googregister():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri=request.base_url + "/callback"
    if 'https' in redirect_uri:
        pass
    else:
        redirect_uri=redirect_uri.replace('http', 'https')
    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route("/google-register/callback")
def registercallback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send request to get tokens! Yay tokens!
    redi=request.base_url
    redi=redi.replace('http', 'https')
    auth=request.url
    auth=auth.replace('http', 'https')
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=auth,
        redirect_url=redi,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        users_email = userinfo_response.json()["email"]
        unique_id = userinfo_response.json()["sub"]
        #picture = userinfo_response.json()["picture"]
        first = userinfo_response.json()["given_name"]
        last = userinfo_response.json()["family_name"]
    else:
        return "User email not available or not verified by Google.", 400

    rows = db.execute("SELECT * FROM users WHERE email = :users_email", users_email=users_email)

    if len(rows) == 1:
        return render_template("apology.html", message="Sorry, there is already an account with this email address")

    username = users_email[0:users_email.index("@")] + str(random.randint(10,99))
    hashed = generate_password_hash(unique_id)
    db.execute("INSERT INTO users (username, hash, email, first, last, newsletter) VALUES (:username, :hashed, :email, :first, :last, 1)", username=username, hashed=hashed, email=users_email, first=first, last=last)
    rows = db.execute("SELECT * FROM users WHERE email = :users_email", users_email=users_email)
    session["user_id"] = rows[0]["id"]
    session["remember_me"] = True
    return redirect("/")


#change password
@app.route('/reset', methods=['POST'])
def reset():
    email = request.form.get('email')
    token = generate_confirmation_token(email, app)
    confirm_url = url_for('password', password_token=token, _external=True)
    
    message = Mail(
        from_email='team@dcyphr.org',
        to_emails=email,
        subject='Change your password',
        html_content="""<p>Please follow this link to change your password.<a href="{0}">Confirm account</a></p><p>If that doesn't work, try copy and pasting this url: {0}""".format(confirm_url))
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY', 'dev'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e)
    return redirect("/login")

#confirm account
@app.route("/confirm/<token>")
def confirm_email(token):
    try:
        email = confirm_token(token, app)
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
    status = db.execute("SELECT confirmed FROM users WHERE email=:email", email=email)
    if status[0]['confirmed'] == 1:
        status = 'Account already confirmed. <a href="/login" style="color: #017bff">Let\'s go!</a>.'
    else:
        db.execute("UPDATE users SET confirmed = 1 WHERE email=:email", email=email)
        status = 'You have confirmed your account. Thanks! You are ready to get started. <a href="/login" style="color: #017bff">Let\'s go!</a>.'
    return render_template("confirm.html", status=status)

@app.route("/unconfirmed/<int:user_id>", methods=["GET", "POST"])
def unconfirmed(user_id):
    if request.method == "GET":
        session.clear()
        return render_template("unconfirmed.html")
    else:
        user = db.execute("SELECT email, first FROM users WHERE id=:user_id", user_id=user_id)[0]
        token = generate_confirmation_token(user['email'], app)
        confirm_url = url_for('confirm_email', token=token, _external=True)
        message = Mail(
            from_email=('team@dcyphr.org', 'dcyphr'),
            to_emails=user['email'],
            subject='Confirm Your dcyphr Account',
                html_content='<h2 style="font-family: Georgia">Welcome to <span style="color: #017bff">dcyphr</span>, {0}!</h2><a href={1}>Please follow this link to confirm your account.</a><p>[{2}] End of message.</p>'.format(user['first'], confirm_url, date.today()))
        try:
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY', 'dev'))
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e)
        return redirect("/unconfirmed/{}".format(user_id))

# displays search results
@app.route("/results")
def results():
    return render_template("results.html")

# admin approves new summaries that are made before they show up on browse
@app.route("/approvals/<int:approval_id>", methods=["GET", "POST"])
@login_required
def approvals(approval_id):
    if request.method == "GET":
        articles = db.execute("SELECT summary, article, link, user_id FROM summary WHERE id=:approval_id", approval_id=approval_id)
        return render_template("approvals.html", articles=articles)
    else:
        summary = request.form.get("summary")
        approve = request.form.get("approve")
        summary_id = db.execute("SELECT id, user_id, article FROM summary WHERE id=:approval_id", approval_id=approval_id)[0]
        # handles disapproval of a summary
        if not approve:
            user_info = db.execute("SELECT email, first FROM users WHERE id=:user_id", user_id=summary_id['user_id'])[0]
            with open('templates/edit_guidelines.html', 'r') as f:
                summary = f.read()
            db.execute("UPDATE summary SET summary=:summary, user_id=NULL, done=CAST(0 AS BIT) WHERE id=:summary_id", summary_id=summary_id['id'], summary=summary)
            db.execute("DELETE FROM history WHERE summary_id=:summary_id", summary_id=summary_id['id'])
            message = Mail(
            from_email=('team@dcyphr.org', 'dcyphr'),
            to_emails=user_info['email'],
            subject='Hi {0}! Unfortunately, your dcyphr distillation was not approved.'.format(user_info['first']),
                html_content="<p>I'm sorry to inform you that your dcyphr distillation for {0} was not accepted. This usually is due to errors that are too significant to be edited by our moderators. Some reasons include but are not limited to: plagiarism, inaccuracy, and profanity. Thank you for your time and energy. We hope you will still continue to make distillations for dcyphr. If you would like to know more, simply reply to this email.<p>[{1}] End of message.</p>".format(summary_id['article'], date.today()))
            try:
                sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY', 'dev'))
                response = sg.send(message)
                print(response.status_code)
                print(response.body)
                print(response.headers)
            except Exception as e:
                print(e)
        # handles approval of a summary
        else:
            user_id = summary_id['user_id']
            user_info = db.execute("SELECT COALESCE(points, 0), first, last, email FROM users WHERE id=:user_id", user_id=user_id)[0]
            points = user_info['coalesce'] + 20
            db.execute("UPDATE users SET points=:points WHERE id=:user_id", points=points, user_id=user_id)
            db.execute("UPDATE summary SET summary = :summary, approved=1, bookmarked=0 WHERE id=:summary_id", summary=summary, summary_id=summary_id['id'])
            message = Mail(
            from_email=('team@dcyphr.org', 'dcyphr'),
            to_emails=user_info['email'],
            subject='Hi {0}! Your dcyphr distillation was approved and published!'.format(user_info['first']),
                html_content="<p>Congrats! Your dcyphr distillation was approved by our team and published on our website. Here's the link for you to share it with your friends: <a clicktracking='off' href='https://www.dcyphr.org/read/{0}'>https://www.dcyphr.org/read/{0}</a></p><p>[{1}] End of message.</p>".format(summary_id['id'], date.today()))
            try:
                sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY', 'dev'))
                response = sg.send(message)
                print(response.status_code)
                print(response.body)
                print(response.headers)
            except Exception as e:
                print(e)
        articles = db.execute("SELECT id, article FROM summary WHERE approved = 0 AND done = CAST(1 AS BIT)")
        length = len(articles)
        return render_template("approval_home.html", articles=articles, length=length)


# homepage of all approvals that need to be checked by admins
@app.route("/approvalhome", methods=["GET"])
@login_required
def approvalhome():
        articles = db.execute("SELECT id, article FROM summary WHERE approved = 0 AND done = CAST(1 AS BIT)")
        length = len(articles)
        return render_template("approval_home.html", articles=articles, length=length)

# allows admin control over bookmarking
@app.route("/bookmarking", methods=["GET", "POST"])
@login_required
def bookmarking():
    if request.method == "GET":
        info = db.execute("SELECT article, doi, bookmarked, bookmarked_date, username, summary.id FROM summary JOIN users ON bookmarked = users.id WHERE bookmarked != 0")
        length = len(info)
        return render_template("bookmarking.html", info=info, length=length)
    if request.method == "POST":
        summary_id = request.form.get("unbookmark")
        db.execute("UPDATE summary SET bookmarked=0 WHERE id=:summary_id", summary_id=summary_id)
        info = db.execute("SELECT article, bookmarked, doi, username, summary.id FROM summary JOIN users ON bookmarked = users.id WHERE bookmarked != 0")
        length = len(info)
        return render_template("bookmarking.html", info=info, length=length)

# shows the help page
@app.route("/about")
def about():
    return render_template("about.html")

# access browser icon information
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')

# errorhandling
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

@app.route('/robots.txt')
@app.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])
