# starting up

Run the following to spin up a flask instance to locally test the web app
`./init`
`flask run`

Run the following to spin up a database instance to interact with the database structure
`phpliteadmin dcyphr.db`

Each route is defined by an `@app.route` and routes that require the user to be logged in have the decorator `@login_required`
If you run into a 500 Internal server error, it is likely that you have either not run `./init` or have not changed the database declaration to `db = SQL("sqlite:///dcyphr.db")` by uncommenting it and commenting out the following line.

`db.execute` is used to run an SQL query on the database and uses string interpolation through setting a variable in the string by preceding it with a colon and then defining the variable as a second, third, etc. argument in the db.execute method.

To integrate API key for mail:
run the following in terminal
    echo "export SENDGRID_API_KEY='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'" > sendgrid.env
    echo "sendgrid.env" >> .gitignore
    source ./sendgrid.env