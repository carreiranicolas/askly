from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.routes.decorators import admin_required
from app.services import ticket_service

web_dashboard_bp = Blueprint("web_dashboard", __name__, url_prefix="/dashboard")


@web_dashboard_bp.route("/")
@login_required
def index():
    return render_template(
        "dashboard/index.html",
        metrics=ticket_service.dashboard_metrics(current_user),
        show_por_area=True,
    )


@web_dashboard_bp.route("/sla")
@admin_required
def sla():
    return render_template(
        "dashboard/sla.html",
        report=ticket_service.sla_report(current_user),
    )
