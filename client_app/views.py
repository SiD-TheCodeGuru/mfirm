from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_login_page():
    ui.query("body").classes("bg-gray-100")

    with ui.column().classes("w-full h-screen items-center justify-center p-4"):
        with ui.card().classes("w-full max-w-sm p-6 shadow-md border rounded-xl bg-white items-center"):
            ui.icon("eco", size="3.5rem").classes("text-green-700")
            ui.label("Mushroom Farm ERP").classes("text-xl font-bold text-green-950 mt-1")
            ui.label("Inventory & Accounting System").classes("text-xs text-gray-500 mb-4")

            username = ui.input("Username or Email").classes("w-full").props("outlined dense")
            password = ui.input("Password").classes("w-full mt-2").props("outlined dense type=password")

            error_label = ui.label("").classes("text-xs text-red-600 mt-1")

            async def handle_login():
                error_label.set_text("")
                if not username.value or not password.value:
                    error_label.set_text("Please enter both username and password.")
                    return

                login_btn.props("loading")
                try:
                    await ApiClient.login(username.value.strip(), password.value.strip())
                    ui.notify("Login successful!", color="positive", position="top")
                    ui.navigate.to("/dashboard")
                except Exception as ex:
                    error_label.set_text(str(ex))
                finally:
                    login_btn.props(remove="loading")

            login_btn = ui.button("Sign In", on_click=handle_login).classes(
                "w-full bg-green-700 hover:bg-green-800 text-white mt-4 py-2 font-semibold rounded-lg shadow-none"
            )

            with ui.column().classes("mt-6 items-center text-center text-xs text-gray-400 leading-tight"):
                ui.label("Demo Credentials:")
                ui.label("• sysadmin / admin123")
                ui.label("• sunrisemanager / manager123")


def render_dashboard_page():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    role = AppSession.get_role()
    is_sys_admin = role == "sys_admin"
    username = AppSession.user.get("username", "User")
    full_name = AppSession.user.get("full_name", username)

    ui.query("body").classes("bg-gray-50")

    with ui.column().classes("w-full max-w-lg mx-auto p-4"):
        # Header Card
        header_color = "bg-blue-50 border-blue-200" if is_sys_admin else "bg-green-50 border-green-200"
        avatar_color = "bg-blue-700" if is_sys_admin else "bg-green-700"

        with ui.card().classes(f"w-full p-4 rounded-xl border shadow-sm {header_color} flex-row items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                with ui.avatar().classes(f"{avatar_color} text-white font-bold"):
                    ui.label(full_name[:2].upper())
                with ui.column().classes("gap-0 leading-tight"):
                    ui.label(full_name).classes("font-bold text-gray-800 text-base")
                    ui.label(f"Role: {role.upper()}").classes("text-xs text-gray-500 font-medium")
                    active_context_label = ui.label(
                        f"Context: {AppSession.active_firm_name or 'None Selected'}"
                    ).classes("text-xs font-semibold text-gray-700 mt-1")

            def logout():
                AppSession.clear()
                ui.notify("Logged out", color="info", position="top")
                ui.navigate.to("/login")

            ui.button(icon="logout", on_click=logout).props("flat round color=negative").tooltip("Logout")

        # Firm Selector for System Admin
        if is_sys_admin:
            with ui.card().classes("w-full p-4 rounded-xl border shadow-sm bg-white mt-3"):
                ui.label("Tenant Firm Context").classes("text-xs font-bold text-gray-500 uppercase tracking-wider")
                firm_select = ui.select(options={}, label="Select Active Firm").classes("w-full mt-1").props("outlined dense")

                async def populate_firms():
                    firms = await ApiClient.fetch_available_firms()
                    options = {f["firm_id"]: f["firm_name"] for f in firms}
                    firm_select.options = options
                    if options:
                        first_id = list(options.keys())[0]
                        firm_select.value = first_id
                        AppSession.active_firm_id = first_id
                        AppSession.active_firm_name = options[first_id]
                        active_context_label.set_text(f"Context: {AppSession.active_firm_name}")

                def on_firm_change(e):
                    AppSession.active_firm_id = e.value
                    AppSession.active_firm_name = firm_select.options.get(e.value, "")
                    active_context_label.set_text(f"Context: {AppSession.active_firm_name}")
                    ui.notify(f"Context switched to: {AppSession.active_firm_name}", color="primary")

                firm_select.on_value_change(on_firm_change)
                ui.timer(0.1, populate_firms, once=True)

        # Operational Modules Header
        ui.label("Operational Modules").classes("text-sm font-bold text-gray-700 uppercase tracking-wider mt-4 mb-1")

        # Reusable Menu Card Builder
        def menu_card(title: str, subtitle: str, icon: str, icon_color: str):
            with ui.card().classes(
                "w-full p-4 rounded-xl border shadow-sm bg-white hover:bg-gray-50 transition-colors cursor-pointer flex-row items-center justify-between mb-2"
            ):
                with ui.row().classes("items-center gap-3"):
                    ui.icon(icon, size="2rem").classes(icon_color)
                    with ui.column().classes("gap-0 leading-tight"):
                        ui.label(title).classes("font-semibold text-gray-800 text-sm")
                        ui.label(subtitle).classes("text-xs text-gray-500")
                ui.icon("chevron_right", size="1.25rem").classes("text-gray-400")

        # Role-Differentiated Modules
        if is_sys_admin:
            menu_card("Global Farm Units", "Register, inspect and activate firm tenants", "domain", "text-blue-600")
            menu_card("Multi-Unit User Admin", "Manage system admins and assign firm managers", "admin_panel_settings", "text-indigo-600")
            menu_card("Consolidated Ledger", "Cross-period spawn & material cost audit", "query_stats", "text-purple-600")
            menu_card("System Health & Audit", "Cluster monitoring and transactional audit logs", "security", "text-slate-600")
        else:
            menu_card("Purchases & Invoices", "Record material invoices & spawn batches", "shopping_cart", "text-green-600")
            menu_card("Batch & Flushes", "Daily harvest yields and flush 1/2/3 logging", "spa", "text-teal-600")
            menu_card("Stock Ledger", "Live quantities of spawn, straw, and packets", "inventory_2", "text-amber-600")
            menu_card("Financial Khata", "Invoices, debtor ledger, and period expenses", "account_balance_wallet", "text-orange-600")