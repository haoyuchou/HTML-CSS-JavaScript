import os
import string

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cash=db.execute("SELECT cash FROM users WHERE id=(?)",session["user_id"])
    cash=cash[0]["cash"] #users current cash

    portfolio=db.execute("SELECT symbol, share FROM portfolio WHERE user_id=(?)", session["user_id"])
    #if not portfolio:
        #return apology("you have no stock")
    overall_total=cash
    for stock in portfolio:
        price=lookup(stock["symbol"])['price']
        total=stock["share"]*price
        stock.update({'price': price, 'total': total})
        overall_total+=total
    return render_template("index.html",cash=cash, stock=portfolio, total=overall_total)


@app.route("/buy", methods=["GET", "POST"])  #post means when inputing data
@login_required
def buy():
    """Buy shares of stock"""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure stock symbol and number of shares was submitted
        if (not request.form.get("symbol")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")

        #ensure number of shares must be integer
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a posative integer", 400)

        # ensure number of shares is valid
        if int(request.form.get("shares")) < 1:
            return apology("must provide valid number of shares (integer)")


        # pull quote from yahoo finance
        quote = lookup(request.form.get("symbol"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # calculate cost of transaction
        cost = int(request.form.get("shares"))* float(quote['price'])

        # check if user has enough cash for transaction
        result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        if cost > result[0]["cash"]:
            return apology("you do not have enough cash for this transaction")

        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash-:cost WHERE id=:id", cost=cost, id=session["user_id"]);

        # add transaction to transaction database
        db.execute("INSERT INTO track (user_id, symbol, share, price, date) VALUES (:user_id, :symbol, :share, :price, :date)",
            user_id=session["user_id"], symbol=quote["symbol"], share=int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # pull number of shares of symbol in portfolio
        curr_portfolio = db.execute("SELECT share FROM portfolio WHERE symbol=:stock AND user_id=:id", stock=quote["symbol"], id=session["user_id"])

        # add to portfolio database
        # if symbol is new, add to portfolio
        if not curr_portfolio:
            db.execute("INSERT INTO portfolio (user_id, symbol, share) VALUES (:user_id, :symbol, :share)",
              user_id=session["user_id"],  symbol=quote["symbol"], share=int(request.form.get("shares")))

        # if symbol is already in portfolio, update quantity of shares and total
        else:
            db.execute("UPDATE portfolio SET share=share+:share WHERE symbol=:symbol AND user_id=:user_id",
                share=int(request.form.get("shares")), symbol=quote["symbol"], user_id=session["user_id"]);

        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():  #datetime!!!!!!!!!!!! for buy,sell and history
    """Show history of transactions"""
    current_history=db.execute("SELECT symbol, share, price, date FROM track WHERE user_id=(?)",session["user_id"])
    if not current_history:
        return apology("you have bo portfolio")
    for value in current_history:
        value["share"]= +(value["share"])
        if value["share"]>0:
            value.update({"b_or_s" : "bought"})
        else:
            value.update({"b_or_s" : "sold"})


    return render_template("history.html", current_history=current_history)
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = (?)", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        #print(rows) # I want to see how rows look like
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
    if request.method == "GET":
        return render_template("quote.html")
    else:

        # ensure name of stock was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol")

        # pull quote from yahoo finance
        symbol = lookup(request.form.get("symbol"))


        # check is valid stock name provided
        if symbol == None:
            return apology("Stock symbol not valid, please try again")

        # stock name is valid
        else:
            return render_template("quoted.html", quote=symbol)

    # else if user reached route via GET (as by clicking a link or via redirect)


'''@app.route("/add_money", methods=["GET", "POST"])
@login_required
def add_money():
    if request.method=="POST":
        addmoney=request.form.get("add_money")
        row=db.execute("SELECT cash FROM users WHERE id=(?)",session["user_id"])
        current_cash=row[0]["cash"]
        db.execute("UPDATE users SET cash = :new_cash WHERE id = :id", new_cash=current_cash+int(addmoney), id=session["user_id"])
        return redirect("/")
    else:
        return render_template("add_money.html")'''


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method=="POST":
        username=request.form.get("username")
        row=db.execute("SELECT * FROM users WHERE username=(?)", username)

        if not username or len(row)==1:
            return apology("no name or already exist")
        password=request.form.get("password")
        confirmation=request.form.get("confirmation")
        if not password or password!=confirmation:
            return apology("no password or no confirm")
        db.execute("INSERT INTO users (username,hash) VALUES (?,?)",username, generate_password_hash(password))
        return redirect("/login")
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():  #need select field for name='symbol'!!!!!!!
    """Sell shares of stock"""
    """Buy shares of stock"""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure stock symbol and number of shares was submitted
        if (not request.form.get("symbol")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares (integer)")

        # pull quote from yahoo finance
        quote = lookup(request.form.get("symbol"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # calculate add of transaction
        add_money= int(request.form.get("shares")) * quote['price']

        # here is cash
        result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        current_cash = result[0]["cash"]

        #check portfolio shares
        portfolio=db.execute("SELECT share FROM portfolio WHERE symbol=:symbol AND user_id=:id", symbol=request.form.get("symbol"), id=session["user_id"])
        #if portfolio[0]["share"]==None:
            #return apology("You don't have this stock")
        if int(portfolio[0]["share"])<int(request.form.get("shares")):
            return apology("You don't enough share")
        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash+:add WHERE id=:id", add=add_money, id=session["user_id"]);

        # add transaction to transaction database
        db.execute("INSERT INTO track (user_id, symbol, share, price, date) VALUES (:user_id, :symbol, :share, :price, :date)",
            user_id=session["user_id"], symbol=quote["symbol"], share = -int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # pull number of shares of symbol in portfolio
        db.execute("UPDATE portfolio SET share=share-:share WHERE symbol=:stock AND user_id=:id", share=int(request.form.get("shares")), stock=quote["symbol"], id=session["user_id"])

        # add to portfolio database


        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
