from flask import render_template, request, redirect, session, flash, current_app
from bson import ObjectId
from datetime import datetime
from . import bank_bp
from flask import jsonify


# ---------------- LOGIN ----------------
@bank_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = current_app.bank_db.users.find_one({
            "login_id": request.form["login_id"],
            "password": request.form["password"]
        })

        if not user:
            flash("Invalid Login", "danger")
            return redirect("/bank/login")

        session["bank_user_id"] = str(user["_id"])
        session["bank_role"] = user["role"]

        if user["role"] == "ADMIN":
            return redirect("/bank/admin")
        elif user["role"] == "BRAVO":
            return redirect("/bank/bravo")
        return redirect("/bank/alpha")

    return render_template("login.html")


# ---------------- ADMIN ----------------
@bank_bp.route("/admin")
def admin():
    if session.get("bank_role") != "ADMIN":
        return redirect("/bank/login")

    users = list(
        current_app.bank_db.users.find(
            {}, {"login_id": 1, "role": 1, "account_no": 1, "balance": 1}
        )
    )

    transactions = list(
        current_app.bank_db.transactions.aggregate([
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"},
            {"$sort": {"created_at": -1}}
        ])
    )

    return render_template("admin_home.html", users=users, transactions=transactions)


# ---------------- BRAVO ----------------
@bank_bp.route("/bravo")
def bravo():
    if session.get("bank_role") != "BRAVO":
        return redirect("/bank/login")

    user = current_app.bank_db.users.find_one(
        {"_id": ObjectId(session["bank_user_id"])}
    )

    return render_template(
        "bravo_home.html",
        data={
            "name": user["login_id"],
            "account_no": user["account_no"],
            "balance": user["balance"]
        }
    )


# ---------------- ALPHA ----------------
@bank_bp.route("/alpha")
def alpha():
    if session.get("bank_role") != "ALPHA":
        return redirect("/bank/login")

    user = current_app.bank_db.users.find_one(
        {"_id": ObjectId(session["bank_user_id"])}
    )

    return render_template(
        "alpha_home.html",
        data={
            "name": user["login_id"],
            "account_no": user["account_no"],
            "balance": user["balance"]
        }
    )


# ---------------- STATEMENT ----------------
@bank_bp.route("/statement")
def statement():
    user_id = ObjectId(session["bank_user_id"])

    data = list(
        current_app.bank_db.transactions.find(
            {"user_id": user_id}
        ).sort("created_at", -1)
    )

    return render_template("statement.html", data=data)


# ---------------- GET ALPHA USER ----------------
@bank_bp.route("/get-alpha-user")
def get_alpha_user():
    account_no = request.args.get("account_no")

    user = current_app.bank_db.users.find_one({
        "account_no": account_no,
        "role": "ALPHA"
    })

    if user:
        return {
            "status": "success",
            "user_id": str(user["_id"]),
            "name": user["login_id"]
        }
    return {"status": "error"}


# ---------------- TRANSFER ----------------
@bank_bp.route("/transfer", methods=["GET", "POST"])
def transfer():
    if session.get("bank_role") != "BRAVO":
        return redirect("/bank/login")

    alpha_users = list(
        current_app.bank_db.users.find({"role": "ALPHA"}, {"login_id": 1})
    )

    if request.method == "POST":
        to_user_id = ObjectId(request.form["alpha_id"])
        amount = float(request.form["amount"])
        bravo_id = ObjectId(session["bank_user_id"])

        bravo = current_app.bank_db.users.find_one({"_id": bravo_id})

        if amount > bravo["balance"]:
            flash("Insufficient Balance", "danger")
            return redirect("/bank/transfer")

        # debit bravo
        current_app.bank_db.users.update_one(
            {"_id": bravo_id},
            {"$inc": {"balance": -amount}}
        )

        # credit alpha
        current_app.bank_db.users.update_one(
            {"_id": to_user_id},
            {"$inc": {"balance": amount}}
        )

        # transactions
        current_app.bank_db.transactions.insert_many([
            {
                "user_id": bravo_id,
                "amount": amount,
                "type": "DEBIT",
                "role": "BRAVO",
                "created_at": datetime.utcnow()
            },
            {
                "user_id": to_user_id,
                "amount": amount,
                "type": "CREDIT",
                "role": "ALPHA",
                "created_at": datetime.utcnow()
            }
        ])

        flash(f"₹ {amount} Debited Successfully", "danger")
        return redirect("/bank/transfer-success")

    return render_template("transfer.html", alpha_user=alpha_users)


# ---------------- TRANSFER SUCCESS ----------------
@bank_bp.route("/transfer-success")
def transfer_success():
    return render_template("transfer_success.html")

#-----------------Forgot-----------------
@bank_bp.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method=="POST":
        login_id=request.form.get("login_id")
        account_no=request.form.get("account_no")
        security_answer=request.form.get("security_answer")
        new_password=request.form.get("new_password")

        user=current_app.bank_db.users.find_one({
            "login_id": login_id,
            "account_no": account_no,
            "security_answer": security_answer
        })

        if not user:
            flash("Invalid details. Please try again.", "danger")
            return redirect("/bank/forgot-password")
        
        current_app.bank_db.users.update_one(
            {"_id": user["_id"]},
            {"$set":{"password": new_password}}
        )
        flash("Password reset successful. Please login.", "success")
        return redirect("/bank/login")
    return render_template("forgot_password.html")

#-----------------API--------------------
@bank_bp.route("/api/pay", methods=["POST"])
def api_pay():
    data = request.json

    username = data.get("username")
    amount = float(data.get("amount"))

    bank_db = current_app.bank_db

    user = bank_db.users.find_one({"login_id": username})
    admin = bank_db.users.find_one({"role": "ADMIN"})

    if not user:
        return jsonify({"status": "error", "msg": "User not found"})

    if user["balance"] < amount:
        return jsonify({"status": "error", "msg": "Insufficient balance"})

    # debit user
    bank_db.users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"balance": -amount}}
    )

    # credit admin
    bank_db.users.update_one(
        {"_id": admin["_id"]},
        {"$inc": {"balance": amount}}
    )

    from datetime import datetime

    bank_db.transactions.insert_many([
        {
            "user_id": user["_id"],
            "amount": amount,
            "type": "DEBIT",
            "role": "SHOP",
            "created_at": datetime.utcnow()
        },
        {
            "user_id": admin["_id"],
            "amount": amount,
            "type": "CREDIT",
            "role": "SHOP",
            "created_at": datetime.utcnow()
        }
    ])

    return jsonify({"status": "success"})

# ---------------- LOGOUT ----------------
@bank_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")



