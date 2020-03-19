import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def readability(summary):
    # sets the values to 0

    letters = 0
    words = 1
    sentences = 0

    # gets text from user

    s = summary

    # calculates length of the text

    length = len(s)

    # considers bad scenarios
    if length == 0:
        words = words - 1
    else:
        if s[0] == " ":
            words = words - 1

        if s[length - 1] == " ":
            words = words - 1

        for i in range(length):
            if s[i].isalpha() == True:
                letters += 1
            # counts words
            if s[i] == " " and s[i - 1] != " ":
                words += 1
         # counts sentences
            if s[i] == "." or s[i] == "?" or s[i] == "!":
                sentences += 1

    # calculates ari and grade
    if words == 0:
        grade = 0
    elif sentences == 0:
        grade = 0
    else:
        L = float(letters) / float(words)
        S = float(words) / float(sentences)
        ari = (4.71 * L) + (0.5 * S) - 21.43
        grade = round(ari)

    if grade <= 1:
        return 1
    elif grade >= 16:
        return 14
    else:
        return grade
