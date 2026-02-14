from flask import Blueprint

stock_bp = Blueprint(
    "stock",
    __name__,
    template_folder="templates/stock",
    static_folder="static",
    url_prefix="/stock"
)

from . import routes
