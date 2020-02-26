About Our Design

For our website we used Flask to implement our website code, HTML to style our website, and SQL to store inputted data.


# SQL DATABASE STRUCTURE
    Our SQL database contains three tables: users, summary, and tasks.
# Users
    The users table stores the users’ usernames, emails, and hashed passwords, along with the number of articles summarized,
    the number of articles reviewed, and the number of likes for each user.
# Summary
    The summary table stores the author’s id, the PMID, and the task id associated with that summary. The columns reviewer_1 and
    reviewer_2 contain the first two reviewers’ user ids to prevent users from reviewing the same article multiple times.
# Tasks
    The tasks table stores the requested articles. The type column contains the value “summary” if the summary has been reviewed
    by 3 people or “review” if the summary still needs to be reviewed by 1 or more people. The done column is set to 0
    when the task is first entered into the database and is incremented to 1 when the article has been summarized. Tasks also stores
    the article title, PMID, the number of times the article has been requested, and the link to the article.


# HOMEPAGE
    When the homepage is accessed, our code checks to see that the SQL tables have been created. If not, the tables are created.
    This was done to avoid errors when we were testing the website functionality. We have included a search bar on our homepage
    that allows users to browse through all articles that have been summarized. The search bar searches article titles, usernames
    of summary authors, and the summaries themselves via the LIKE function in SQL. The results are then stored in a dictionary and
    the articles that matched are returned and displayed via “results.html”.

# BROWSE
    Our browse page displays the articles summarized and the summary author in a table. The article title is hyperlinked to a dynamic
    sub-route that takes the user to the page /read/“PMID” (where PMID is the PMID of the article). This sub route displays the article
    title, summary author, summary, and link that were passed to the HTML file using Jinja. We also have included a function that allows
    users to like or dislike. Once the user has liked or disliked the article, the like function is disabled.

# REQUEST
    Request allows users request article summaries. The page has article name, PMID, and link as required fields. When request is posted,
    our code checks to see if the article has been requested. If it has, the number of requests is updated in the database. If the PMID
    has been requested but the inputted article title does not match our database, an error is returned.

# CONTRIBUTE
    Contribute shows a list of requested articles that have not been reviewed by 3 people, indicated by the type in the tasks table. Like
    browse, the article title is hyperlinked and routed to a dynamic sub-link /review/“PMID”.  Here the user can submit a form either passing
    or not passing the article. When the user tries to submit their review, our code checks the summary table columns “reviewer_1" and
    “reviewer_2” to see if the user has already reviewed the article. It also prohibits the author from reviewing their own summary. If the
    user has already reviewed the article or is the author of the summary, an error message appears. If the user has not already reviewed the
    article and passes the summary, the number of reviews is incremented. If the summary has received 3 passing reviews, it's type on the task
    page is changed from "review" to "summary" and the article no longer shows up on the contribute page. If the user does not pass the article,
    the summary is removed from the database and the “done” column in the tasks table is set back to 0.

# ABOUT
    The about page contains hardcoded information about the website and creators.

# PROFILE
    Profile is a dynamically routed page /profile/“user_id” that shows how many articles the user has summarized, retrieved from the users table,
    and a progress bar that shows user status. The bar fills as the user summarizes more articles. The user has the ability to change their p
    assword through the hyperlink.

# REGISTER
    Register allows users to create an account. When posted, our code checks that the username has not been taken, that the email is valid,
    and that the password and confirmation match.