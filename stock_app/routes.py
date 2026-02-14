from flask import render_template, redirect, session, request, current_app, flash
from bson import ObjectId
from . import stock_bp


# ================= LOGIN =================
@stock_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = current_app.bank_db.users.find_one({
            "login_id": request.form["login_id"],
            "password": request.form["password"]
        })

        if not user:
            return render_template("stock_login.html", error="Invalid Login")

        session["stock_user_id"] = str(user["_id"])
        session["stock_login_id"] = user["login_id"]

        # 🔴 CHANGE: ensure demat wallet (safe upsert)
        current_app.bank_db.demat_wallet.update_one(
            {"user_id": user["_id"]},
            {"$setOnInsert": {"balance": 0}},
            upsert=True
        )

        return redirect("/stock/dashboard")

    return render_template("stock_login.html")


# ================= DASHBOARD =================
@stock_bp.route("/dashboard")
def dashboard():
    if "stock_user_id" not in session:
        return redirect("/stock/login")

    # 🔴 CHANGE: always fetch ALL stocks
    stocks = list(current_app.bank_db.stocks.find())

    stocks_data = [
        (str(s["_id"]), s["name"], s["price"])
        for s in stocks
    ]

    return render_template(
        "dashboard.html",
        stocks=stocks_data,
        username=session.get("stock_login_id")
    )


# ================= STOCK DETAIL =================
@stock_bp.route("/stocks/<id>")
def stock(id):
    stock = current_app.bank_db.stocks.find_one({"_id": ObjectId(id)})

    # 🔴 CHANGE: send frontend-required keys
    return render_template(
        "stock.html",
        stock={
            "id": str(stock["_id"]),
            "name": stock["name"],
            "price": stock["price"],
            "change": "+2",        # dummy for UI
            "percent": "2"         # dummy for UI
        }
    )


# ================= BUY =================
@stock_bp.route("/buy", methods=["POST"])
def buy_stock():
    user_id = ObjectId(session["stock_user_id"])
    stock_id = ObjectId(request.form["stock_id"])
    investment = float(request.form["investment"])

    wallet = current_app.bank_db.demat_wallet.find_one({"user_id": user_id})
    if wallet["balance"] < investment:
       flash("Insufficient demat balance", "danger")
       return redirect(f"/stock/stocks/{stock_id}")


    # debit demat
    current_app.bank_db.demat_wallet.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -investment}}
    )

    stock = current_app.bank_db.stocks.find_one({"_id": stock_id})

    # 🔴 CHANGE: portfolio safe upsert
    current_app.bank_db.portfolio.update_one(
        {"user_id": user_id, "stock_id": stock_id},
        {
            "$inc": {"quantity": 1, "investment": investment},
            "$setOnInsert": {"stock_name": stock["name"]}
        },
        upsert=True
    )

    return redirect("/stock/portfolio")


# ================= SELL =================
@stock_bp.route("/sell", methods=["POST"])
def sell_stock():
    user_id = ObjectId(session["stock_user_id"])
    stock_id = ObjectId(request.form["stock_id"])
    investment = float(request.form["investment"])

    holding = current_app.bank_db.portfolio.find_one({
        "user_id": user_id,
        "stock_id": stock_id
    })

    if not holding or holding["investment"] < investment:
       flash("Invalid sell amount", "danger")
       return redirect(f"/stock/stocks/{stock_id}")


    current_app.bank_db.portfolio.update_one(
        {"_id": holding["_id"]},
        {"$inc": {"quantity": -1, "investment": -investment}}
    )

    current_app.bank_db.demat_wallet.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": investment}}
    )

    # 🔴 CHANGE: cleanup zero qty
    current_app.bank_db.portfolio.delete_many({"quantity": {"$lte": 0}})

    return redirect("/stock/portfolio")


# ================= PORTFOLIO =================
@stock_bp.route("/portfolio")
def portfolio():
    data = list(
        current_app.bank_db.portfolio.find(
            {"user_id": ObjectId(session["stock_user_id"])}
        )
    )

    table = [
        (d["stock_name"], d["quantity"], 100, d["investment"])
        for d in data
    ]

    return render_template(
        "portfolio.html",
        data=table,
        username=session.get("stock_login_id")
    )


# ================= DEMAT =================
@stock_bp.route("/demat")
def demat():
    wallet = current_app.bank_db.demat_wallet.find_one(
        {"user_id": ObjectId(session["stock_user_id"])}
    )

    return render_template(
        "demat.html",
        balance=wallet["balance"],
        username=session.get("stock_login_id")
    )


# ================= DEMAT ADD =================
@stock_bp.route("/demat/add", methods=["POST"])
def demat_add():
    amount = float(request.form["amount"])
    user_id = ObjectId(session["stock_user_id"])

    user = current_app.bank_db.users.find_one({"_id": user_id})
    if user["balance"] < amount:
      flash("Insufficient bank balance", "danger")
      return redirect("/stock/demat")

    current_app.bank_db.users.update_one(
        {"_id": user_id},
        {"$inc": {"balance": -amount}}
    )

    current_app.bank_db.demat_wallet.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}}
    )

    return redirect("/stock/demat")


# ================= DEMAT WITHDRAW =================
@stock_bp.route("/demat/withdraw", methods=["POST"])
def demat_withdraw():
    amount = float(request.form["amount"])
    user_id = ObjectId(session["stock_user_id"])     

    wallet = current_app.bank_db.demat_wallet.find_one({"user_id": user_id})
    if wallet["balance"] < amount:
      flash("Insufficient demat balance", "danger")
      return redirect("/stock/demat")

    current_app.bank_db.demat_wallet.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -amount}}
    )

    current_app.bank_db.users.update_one(
        {"_id": user_id},
        {"$inc": {"balance": amount}}
    )

    return redirect("/stock/demat")


# ================= LOGOUT =================
@stock_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/stock/login")
