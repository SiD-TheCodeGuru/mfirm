from client_app.views.login_view import render_login_view
from client_app.views.dashboard_view import render_dashboard_view
from client_app.views.user_admin_view import render_user_admin_view
from client_app.views.items_view import render_items_view
from client_app.views.stock_view import render_stock_view
from client_app.views.purchase_view import render_purchases_view
from client_app.views.expenses_view import render_expenses_view
from client_app.views.batches_view import render_batches_view
from client_app.views.reports_view import render_reports_view

__all__ = [
    "render_login_view",
    "render_dashboard_view",
    "render_user_admin_view",
    "render_items_view",
    "render_stock_view",
    "render_purchases_view",
    "render_expenses_view",
    "render_batches_view",
    "render_reports_view",
]