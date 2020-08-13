# [dcyphr] (https://www.dcyphr.org) ![Alt](/static/logos/dcyphr_logo_blue.png "LOGO")

dcyphr is a web application built in Flask/SQL/HTML/JS. It is a crowd-sourced platform informed by NLP to make academic research more
accessible. [Learn more] (https://linktr.ee/dcyphr)

* **Register** and **login**
* **Request** articles to be distilled
* **Browse** knowledge base through *Search* or *Explore*
* **Interact** with articles by *liking*, *endorsing*, *sharing*, *commenting*, raising *issues*.

![Alt](/static/landing/landing.png "Landing")

## Installation

Clone this repositiory `git clone https://github.com/dcyphr/dcyphr.git`.
Navigate to the repository on your local machine.

Set up a python3 virtual environment.
```
python3 -m venv myenv
source myenv/bin/activate
```

Install requirements
`pip install -r requirements.txt`

Run the setup script
```
source ./setup.sh
```

You should have the Flask app running on your local environment!

## Getting started

Each route is defined by an `@app.route` and routes that require the user to be logged in have the decorator `@login_required`

`db.execute` is used to run an SQL query on the database and uses string interpolation through setting a variable in the string by preceding it with a colon and then defining the variable as a second, third, etc. argument in the db.execute method.

## TODO

* Train NLP on [PLOS dataset] (http://deepdive.stanford.edu/opendata/#plos-public-library-of-science)
* Integrate NLP feature for automatic distillation
    1. Article URL -> distillation
    2. Article DOI -> distillation
    3. Article PDF -> distillation
    4. Ability to request *human pruning* or *mark as correct*
* Generate wrapper for NLP to periodically retrain on new data
* Integrate Stripe payment and create premium features
* React overhaul