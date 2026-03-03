from flask import render_template, request, redirect, session, flash, current_app
from bson import ObjectId
from datetime import datetime
from . import bank_bp
from flask import jsonify
from flask import send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pytz

ist = pytz.timezone("Asia/Kolkata")

def to_ist(dt):
    return dt.replace(tzinfo=pytz.utc).astimezone(ist)

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

    # ✅ DATE FORMAT FIX
    for t in transactions:
        dt = to_ist(t["created_at"])
        t["created_at"] = dt.strftime("%d/%m/%Y %I:%M %p")
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

    # ✅ FORMAT DATE FOR UI
    for tx in data:
        dt = to_ist(tx["created_at"])
        tx["created_at"] = dt.strftime("%d/%m/%Y %I:%M %p")

    return render_template("statement.html", data=data)

# ---------------- STATEMENT PDF ----------------
@bank_bp.route("/statement/pdf")
def download_statement_pdf():
    from datetime import datetime

    user_id = ObjectId(session["bank_user_id"])
    user = current_app.bank_db.users.find_one({"_id": user_id})

    transactions = list(
        current_app.bank_db.transactions.find(
            {"user_id": user_id}
        ).sort("created_at", -1)
    )

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 50

    # -------- HEADER --------
    p.setFont("Helvetica-Bold", 16)
    p.drawString(170, y, "SmartPay Bank Statement")

    # -------- USER DETAILS --------
    y -= 35
    p.setFont("Helvetica", 11)
    p.drawString(50, y, f"Name: {user['login_id']}")
    y -= 18
    p.drawString(50, y, f"Account No: {user['account_no']}")
    y -= 18
    p.drawString(50, y, f"Role: {user['role']}")

    # -------- TABLE HEADER --------
    y -= 30
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, y, "Date")
    p.drawString(170, y, "Amount")
    p.drawString(260, y, "Type")
    p.drawString(330, y, "Role")

    y -= 8
    p.line(50, y, 550, y)
    y -= 18

    # -------- TABLE DATA --------
    p.setFont("Helvetica", 10)

    for tx in transactions:
        if y < 50:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)

        # ✅ DATE FORMAT FIX (DD/MM/YYYY HH:MM)
        dt = to_ist(tx["created_at"])
        formatted_date = dt.strftime("%d/%m/%Y %I:%M %p")

        p.drawString(50, y, formatted_date)
        p.drawString(170, y, f"Rs {tx['amount']:.2f}")
        p.drawString(260, y, tx["type"])
        p.drawString(330, y, tx["role"])

        y -= 18

    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="SmartPay_Statement.pdf",
        mimetype="application/pdf"
    )

# ---------------- GET ALPHA USER ----------------
# @bank_bp.route("/get-alpha-user")
# def get_alpha_user():
#     account_no = request.args.get("account_no")

#     user = current_app.bank_db.users.find_one({
#         "account_no": account_no,
#         "role": "ALPHA"
#     })

#     if user:
#         return {
#             "status": "success",
#             "user_id": str(user["_id"]),
#             "name": user["login_id"]
#         }
#     return {"status": "error"}

# ---------------- GET USER BY NAME ----------------
@bank_bp.route("/get-alpha-by-name")
def get_alpha_by_name():
    name = request.args.get("name")

    user = current_app.bank_db.users.find_one({
        "login_id": name,
        "role": "ALPHA"
    })

    if user:
        return {
            "status": "success",
            "account_no": user["account_no"],
            "user_id": str(user["_id"])
        }
    return {"status": "error"}

# ---------------- TRANSFER ----------------
@bank_bp.route("/transfer", methods=["GET", "POST"])
def transfer():
    if session.get("bank_role") not in ["BRAVO", "ADMIN"]:
        return redirect("/bank/login")

    if request.method == "POST":
        to_user_id = ObjectId(request.form["alpha_id"])
        amount = float(request.form["amount"])
        user_id = ObjectId(session["bank_user_id"])

        user = current_app.bank_db.users.find_one({"_id": user_id})

        if amount > user["balance"]:
            flash("Insufficient Balance", "danger")
            return redirect("/bank/transfer")

        # ❌ NO DEBIT HERE
        # ❌ NO CREDIT HERE
        # ❌ NO TRANSACTION HERE

        # store pending payment
        session["pending_transfer"] = {
            "to_user_id": str(to_user_id),
            "amount": amount
        }

        return redirect("/bank/enter-pin")

    return render_template("transfer.html")
# @bank_bp.route("/transfer", methods=["GET", "POST"])
# def transfer():
#     if session.get("bank_role") not in ["BRAVO", "ADMIN"]:
#         return redirect("/bank/login")

#     alpha_users = list(
#         current_app.bank_db.users.find({"role": "ALPHA"}, {"login_id": 1})
#     )

#     if request.method == "POST":
#         to_user_id = ObjectId(request.form["alpha_id"])
#         amount = float(request.form["amount"])
#         bravo_id = ObjectId(session["bank_user_id"])

#         bravo = current_app.bank_db.users.find_one({"_id": bravo_id})

#         if amount > bravo["balance"]:
#             flash("Insufficient Balance", "danger")
#             return redirect("/bank/transfer")

#         # debit bravo
#         current_app.bank_db.users.update_one(
#             {"_id": bravo_id},
#             {"$inc": {"balance": -amount}}
#         )

#         # credit alpha
#         current_app.bank_db.users.update_one(
#             {"_id": to_user_id},
#             {"$inc": {"balance": amount}}
#         )

#         # transactions
#         current_app.bank_db.transactions.insert_many([
#             {
#                 "user_id": bravo_id,
#                 "amount": amount,
#                 "type": "DEBIT",
#                 "role": "BRAVO",
#                 "created_at": datetime.utcnow()
#             },
#             {
#                 "user_id": to_user_id,
#                 "amount": amount,
#                 "type": "CREDIT",
#                 "role": "ALPHA",
#                 "created_at": datetime.utcnow()
#             }
#         ])

#         flash(f"₹ {amount} Debited Successfully", "danger")
#         # return redirect("/bank/transfer-success")
#         # store temp transfer in session
#         session["pending_transfer"] = {
#             "to_user_id": str(to_user_id),
#             "amount": amount
#         }

#         return redirect("/bank/enter-pin")

#     return render_template("transfer.html", alpha_user=alpha_users)

# ---------------- ENTER PIN ----------------
@bank_bp.route("/enter-pin", methods=["GET", "POST"])
def enter_pin():
    if "pending_transfer" not in session:
        return redirect("/bank/transfer")

    user_id = ObjectId(session["bank_user_id"])
    user = current_app.bank_db.users.find_one({"_id": user_id})

    if request.method == "POST":
        entered_pin = request.form["pin"]

        # ❌ wrong pin
        if str(user.get("pin")) != str(entered_pin):
            flash("Invalid PIN", "danger")
            return redirect("/bank/enter-pin")

        # ✅ correct pin → DO TRANSFER
        data = session.pop("pending_transfer")
        to_user_id = ObjectId(data["to_user_id"])
        amount = float(data["amount"])

        # debit
        current_app.bank_db.users.update_one(
            {"_id": user_id},
            {"$inc": {"balance": -amount}}
        )

        # credit
        current_app.bank_db.users.update_one(
            {"_id": to_user_id},
            {"$inc": {"balance": amount}}
        )

        # transaction log
        current_app.bank_db.transactions.insert_many([
            {
                "user_id": user_id,
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

        flash("Payment Successful", "success")
        return redirect("/bank/transfer-success")

    return render_template("enter_pin.html")

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
    merchant = data.get("merchant", "ADMIN")  # DEFAULT ADMIN

    bank_db = current_app.bank_db

    # buyer
    user = bank_db.users.find_one({"login_id": username})

    # merchant wallet
    merchant_user = bank_db.users.find_one({"login_id": merchant})

    if not user:
        return jsonify({"status": "error", "msg": "User not found"})

    if not merchant_user:
        return jsonify({"status": "error", "msg": f"{merchant} wallet not found"})

    if user["balance"] < amount:
        return jsonify({"status": "error", "msg": "Insufficient balance"})

    # debit buyer
    bank_db.users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"balance": -amount}}
    )

    # credit merchant
    bank_db.users.update_one(
        {"_id": merchant_user["_id"]},
        {"$inc": {"balance": amount}}
    )

    bank_db.transactions.insert_many([
        {
            "user_id": user["_id"],
            "amount": amount,
            "type": "DEBIT",
            "role": "DEBIT_PURCHASE",
            "created_at": datetime.utcnow()
        },
        {
            "user_id": merchant_user["_id"],
            "amount": amount,
            "type": "CREDIT",
            "role": "CREDIT_SALE",
            "created_at": datetime.utcnow()
        }
    ])

    return jsonify({"status": "success"})

# ---------------- API LOGIN ----------------
@bank_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.json

    user = current_app.bank_db.users.find_one({
        "login_id": data.get("login_id"),
        "password": data.get("password")
    })

    if not user:
        return jsonify({"status": "error"})

    return jsonify({"status": "success"})

# ---------------- LOGOUT ----------------
@bank_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")
