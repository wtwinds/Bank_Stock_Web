from flask import Flask, render_template
from bank_app import bank_bp
from stock_app import stock_bp
from tambola_app import tambola_bp
import config

app = Flask(__name__)
app.secret_key = "master_secret"


#mongodb (bank app)
app.bank_db=config.bank_db

# register blueprint
app.register_blueprint(bank_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(tambola_bp)

@app.route("/")
def home():
    return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
