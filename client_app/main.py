import sys
from pathlib import Path


# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nicegui import ui
from client_app.views import (
    render_login_view,
    render_dashboard_view,
    render_user_admin_view,
    render_items_view,
    render_stock_view,
    render_purchases_view,
    render_expenses_view,
    render_batches_view,
    render_reports_view
)


@ui.page("/")
def index():
    ui.navigate.to("/login")


@ui.page("/login")
def login():
    render_login_view()


@ui.page("/dashboard")
def dashboard():
    render_dashboard_view()

@ui.page("/admin/users")
def user_admin():
    render_user_admin_view()

@ui.page("/items")
def items():
    render_items_view()

@ui.page("/stock")
def stock():
    render_stock_view()
@ui.page("/purchases")
def purchases():
    render_purchases_view()

@ui.page("/expenses")
def expenses():
    render_expenses_view()
@ui.page("/batches")
def batches():
    render_batches_view()

@ui.page("/reports")
def reports():
    render_reports_view()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Mushroom Farm ERP",
        port=8553,
        reload=False,
        show=True,
    )