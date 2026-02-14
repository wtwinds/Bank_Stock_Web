from flask import Blueprint

bank_bp = Blueprint(
    "bank",
    __name__,
    template_folder="templates/bank",
    static_folder="static",
    url_prefix="/bank"
)

# 🔥 VERY IMPORTANT
from . import routes
