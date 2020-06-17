# setting up local environment
Clone this repositiory using git clone.
Navigate to the repository on your local machine.

Set up a python virtual environment.
```
sudo pip install virtualenv
virtualenv myenv
source myenv/bin/activate
```
Make sure you are running Python 3
```
python --version
```
Install requirements
`pip install -r requirements.txt`

Install Heroku CLI and get the database URL (use DATABASE_URL)
`heroku config -a dcyphr`

Set environment variables
```
export FLASK_APP=application.py FLASK_ENV=development DATABASE_URL={whatever you got from the previous step}
```
Should be good to go!

# starting up

Run the following to spin up a flask instance to locally test the web app
`./init`
`flask run`

If you want to use the local database to run tests, run the following to spin up a database instance to interact with the database structure
`phpliteadmin dcyphr.db`

Each route is defined by an `@app.route` and routes that require the user to be logged in have the decorator `@login_required`
If you run into a 500 Internal server error, it is likely that you have either not run `./init` or have not changed the database declaration to `db = SQL("sqlite:///dcyphr.db")` by uncommenting it and commenting out the following line.

`db.execute` is used to run an SQL query on the database and uses string interpolation through setting a variable in the string by preceding it with a colon and then defining the variable as a second, third, etc. argument in the db.execute method.

To integrate API key for mail:
run the following in terminal
    echo "export SENDGRID_API_KEY='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'" > sendgrid.env
    echo "sendgrid.env" >> .gitignore
    source ./sendgrid.env
