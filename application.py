from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    totalcash = 0
    shares = db.execute("SELECT quantity , symbol FROM portfolio WHERE id = :id",id=session["user_id"])
    i=0
    for share in shares:
        symbol= shares[i]["symbol"]
        quantity=shares[i]["quantity"]
        stock = lookup(symbol)
        cost = stock["price"] * quantity
        totalcash += cost
        i+=1
    userbal= db.execute("SELECT cash FROM users WHERE id=:id",id = session["user_id"])
    totalcash+=userbal[0]["cash"]

    display = db.execute("SELECT * FROM portfolio WHERE id=:id",id = session["user_id"])

    return render_template("index.html",display=display, bal = usd(userbal[0]["cash"]), asset=usd(totalcash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    if request.method == "POST":
        deets = lookup(request.form.get("symbol"))
        if not deets:
            return apology("Incorrect Symbol")

        quant=int(request.form.get("quantity") )
        if quant <0:
            return apology("Invalid Quantity")

        cash = db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])
        name=deets["name"]
        symbol=deets["symbol"]
        price=deets["price"]

        if float(cash[0]["cash"] ) >= quant * price:
            db.execute("INSERT INTO histories (id,Symbol, Quantity , Price) VALUES (:id,:symbol,:quant,:price)",symbol=symbol,quant=quant,price=usd(price),id=session["user_id"])

            db.execute("UPDATE users SET cash= cash - :purchase WHERE id=:id",id=session["user_id"],purchase=price * float(quant) )

            users_shares = db.execute("SELECT quantity FROM portfolio WHERE id=:id AND symbol=:symbol",id=session["user_id"], symbol=symbol)

            if not users_shares:
                db.execute("INSERT INTO portfolio (name, quantity, price, total, symbol, id) VALUES(:name, :quantity, :price, :total, :symbol, :id)",name=name, quantity=quant, price=usd(deets["price"]), total=usd(quant * deets["price"]), symbol=symbol, id=session["user_id"])
                return redirect(url_for("index"))
            else:
                shares_total=users_shares[0]["quantity"] + quant
                db.execute("UPDATE portfolio SET quantity=:quantity WHERE id=:id AND symbol=:symbol",quantity=shares_total, id=session["user_id"],symbol=symbol)
                db.execute("UPDATE portfolio SET total=:total WHERE id=:id AND symbol=:symbol",total=usd(shares_total * deets["price"]), id=session["user_id"],symbol=symbol)
                return redirect(url_for("index"))
        else:
            return apology("Insufficient funds")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    hists = db.execute("SELECT * FROM histories WHERE id=:id",id=session["user_id"])

    return render_template("history.html",display=hists)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        deets = lookup(request.form.get("symbol"))
        if not deets:
            return apology("Incorrect Symbol")

        return render_template("quoted.html" , stock=deets)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("Username missing")

        elif not request.form.get("password"):
            return apology("Password Missing")

        elif not request.form.get("confirmpassword"):
            return apology("Password confirmation missing")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username does not exists
        if len(rows) == 1:
            return apology("Username already exists")

        if request.form.get("confirmpassword") != request.form.get("password"):
            return apology("Passwords do not match")

        hash1 = pwd_context.hash(request.form.get("password"))

        db.execute("INSERT INTO users (username,hash) VALUES(:username, :hash)", username=request.form.get("username"),hash=hash1)

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    totalcash = 0
    shares = db.execute("SELECT quantity , symbol FROM portfolio WHERE id = :id",id=session["user_id"])
    for share in shares:
            symbol= shares[0]["symbol"]
            quantity=shares[0]["quantity"]
            stock = lookup(symbol)
            cost = stock["price"] * quantity
            totalcash += cost

    userbal= db.execute("SELECT cash FROM users WHERE id=:id",id = session["user_id"])
    totalcash+=userbal[0]["cash"]

    display = db.execute("SELECT * FROM portfolio WHERE id=:id",id = session["user_id"])

    if request.method == "POST":
        deets = lookup(request.form.get("symbol"))
        if not deets:
            return apology("Incorrect Symbol")

        quant=int(request.form.get("quantity") )
        if quant <0:
            return apology("Invalid Quantity")

        cash = db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])
        name_ent=deets["name"]
        symbol_ent=deets["symbol"]
        price=deets["price"]
        j=0
        for share in shares:
            symbol= shares[j]["symbol"]
            quantity=shares[j]["quantity"]
            if symbol == symbol_ent:
                if quant <= quantity:
                    db.execute("INSERT INTO histories (id,Symbol, Quantity , Price) VALUES (:id,:symbol,:quant,:price)",symbol=symbol,quant=-quant,price=usd(price),id=session["user_id"])
                    db.execute("UPDATE users SET cash=cash + :purchase WHERE id=:id",id=session["user_id"],purchase=price*quant)
                    quantity -=quant
                    if quantity == 0:
                        db.execute("DELETE FROM portfolio WHERE id=:id AND symbol=:symbol",id=session["user_id"],symbol=symbol)
                        return redirect(url_for("index"))

                    db.execute("UPDATE portfolio SET quantity= :quantity WHERE id=:id AND symbol=:symbol",quantity=quantity,id=session["user_id"],symbol=symbol)
                    db.execute("UPDATE portfolio SET total=:total WHERE id=:id AND symbol=:symbol",total=usd(price*quantity),id=session["user_id"],symbol=symbol)
                    return redirect(url_for("index"))
                else:
                    return apology("Insufficient quantity")
            j+=1

        return apology("You don't own this share")
    else:
        return render_template("sell.html",display=display)

@app.route("/password", methods=["GET", "POST"])
def password():
    """Change Password."""
    if request.method == "POST":
        if not request.form.get("currentpassword"):
            return apology("Current password missing")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

        # ensure username exists and password is correct
        if not pwd_context.verify(request.form.get("currentpassword"), rows[0]["hash"]):
            return apology("invalid current password")

        if not request.form.get("newpassword"):
            return apology("New password Missing")

        elif not request.form.get("confirmpassword"):
            return apology("Password confirmation missing")

        if request.form.get("confirmpassword") != request.form.get("newpassword"):
            return apology("Passwords do not match")

        hash1 = pwd_context.hash(request.form.get("newpassword"))

        db.execute("UPDATE users set hash=:hash WHERE id=:id", hash=hash1,id=session["user_id"])

        return redirect(url_for("index"))

    else:
        return render_template("password.html")
