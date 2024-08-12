import os
import pytz

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session.get("user_id")
    cash = db.execute("SELECT cash FROM users WHERE id=(?)", id)[0]["cash"]
    rows = db.execute("SELECT * FROM portfolio WHERE user_id=(?)", id)
    total = cash
    for row in rows:
        price = lookup(row["symbol"])["price"]
        row["price"] = price
        total += row["share"] * price

    return render_template("index.html", portfolios=rows, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        if not symbol:
            return apology("Missing symbol")
        share = request.form.get("share")
        if not share:
            return apology("Missing share")
        share = int(share)
        price = lookup(symbol)["price"]
        if not price:
            return apology("Invalid symbol")
        time = datetime.now(pytz.timezone("US/Eastern"))
        id = session.get("user_id")

        cash = db.execute("SELECT cash FROM users WHERE id=(?)", id)[0]["cash"]
        if share * price > cash:
            return apology("Can't afford")

        db.execute("UPDATE users SET cash = cash - (?) WHERE id=(?)", (share * price), id)

        db.execute("INSERT INTO history (symbol, price, user_id, share, time) VALUES (?, ?, ?, ?, ?)", symbol, price, id, share, time)

        if not db.execute("SELECT * FROM portfolio WHERE user_id=(?) AND symbol=(?)", id, symbol):
            db.execute("INSERT INTO portfolio (symbol, share, user_id) VALUES (?, ?, ?)", symbol, share, id)
        else:
            db.execute("UPDATE portfolio SET share = share + (?) WHERE user_id=(?) AND symbol=(?)", share, id, symbol)

        flash("Bought!")
        return redirect("/")



    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session.get("user_id")
    rows = db.execute("SELECT * FROM history WHERE user_id=(?)", id)
    deposit = db.execute("SELECT * FROM deposit WHERE user_id=(?)", id)

    return render_template("history.html", history=rows, deposit=deposit)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        if stock:
            return render_template("quoted.html", symbol=stock["symbol"], price=stock["price"])

        else:
            return apology("Invalid Symbol")

    else:
        stocks = db.execute("SELECT * FROM stocks")
        return render_template("quote.html", stocks=stocks)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_again = request.form.get("password_again")

        if not username:
            return apology("Username missing")

        if not password:
            return apology("password missing")

        if password_again != password:
            return apology("You entered different passwords")

        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))

        except ValueError:
            return apology("Username already exist")

        flash("Registered!")
        session["user_id"] = db.execute("SELECT id FROM users WHERE username=(?)", username)[0]["id"]
        session["username"] = username
        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing symbol")

        share = request.form.get("share")
        if not share:
            return apology("Missing share")
        share = int(share)

        price = lookup(symbol)["price"]
        time = datetime.now(pytz.timezone("US/Eastern"))
        id = session.get("user_id")

        hold = db.execute("SELECT share FROM portfolio WHERE user_id=(?) AND symbol=(?)", id, symbol)[0]["share"]
        if share > hold:
            return apology("More than you have")

        db.execute("UPDATE portfolio SET share = share - (?) WHERE user_id=(?) AND symbol=(?)", share, id, symbol)

        db.execute("UPDATE users SET cash = cash + (?) WHERE id=(?)", (share * price), id)

        db.execute("INSERT INTO history (symbol, price, user_id, share, time) VALUES (?, ?, ?, ?, ?)", symbol, price, id, (-1 * share), time)

        if db.execute("SELECT share FROM portfolio WHERE user_id=(?) AND symbol=(?)", id, symbol)[0]["share"] == 0:
            db.execute("DELETE FROM portfolio WHERE user_id=(?) AND symbol=(?)", id, symbol)


        flash("Sold!")
        return redirect("/")



    else:
        id = session.get("user_id")
        rows = db.execute("SELECT * FROM portfolio WHERE user_id=(?)", id)

        return render_template("sell.html", portfolios=rows)



@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        cash = request.form.get("cash")
        if not cash:
            return apology("Please enter an amount")

        id = session.get("user_id")
        time = datetime.now(pytz.timezone("US/Eastern"))
        db.execute("UPDATE users SET cash = cash + (?) WHERE id=(?)", cash, id)
        db.execute("INSERT INTO deposit (user_id, amount, time) VALUES (?, ?, ?)", id, cash, time)

        flash("Deposited!")
        return redirect("/")


    else:
        return render_template("deposit.html")


@app.route("/change", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        new_password_again = request.form.get("new_password_again")
        id = session.get("user_id")

        if not check_password_hash(db.execute("SELECT hash FROM users WHERE id=(?)", id)[0]["hash"], current_password):
            return apology("Wrong password")

        if not new_password:
            return apology("Password missing")

        if new_password_again != new_password:
            return apology("You entered different passwords")

        db.execute("UPDATE users SET hash=(?) WHERE id=(?)", generate_password_hash(new_password), id)

        flash("Password Changed!")
        return redirect("/")


    else:
        return render_template("change.html")





