from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_user_admin_view():
    # Role Guard: sys_admin only
    if not AppSession.is_logged_in() or AppSession.get_role() != "sys_admin":
        ui.notify("Unauthorized access. Sys Admin required.", color="negative")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")

    with ui.column().classes("w-full max-w-lg mx-auto p-4"):
        # Top Navigation Bar
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                ui.label("Register Farm User").classes("text-lg font-bold text-gray-800")
            ui.icon("person_add", size="1.75rem").classes("text-blue-700")

        # Form Card
        with ui.card().classes("w-full p-6 rounded-xl border shadow-sm bg-white gap-3"):
            ui.label("Account & Firm Credentials").classes(
                "text-xs font-bold text-gray-400 uppercase tracking-wider mb-1"
            )

            # Role Selection
            role_select = ui.select(
                options={"firm_admin": "Firm Admin (Farm Manager)", "sys_admin": "System Admin (Global)"},
                value="firm_admin",
                label="Assigned System Role",
            ).classes("w-full").props("outlined dense")

            # Dynamic Firm Selector
            firm_select = ui.select(
                options={},
                label="Assign to Tenant Firm",
            ).classes("w-full").props("outlined dense")

            # Toggle firm selection requirement based on role
            def on_role_change(e):
                if e.value == "sys_admin":
                    firm_select.set_visibility(False)
                    firm_select.value = None
                else:
                    firm_select.set_visibility(True)

            role_select.on_value_change(on_role_change)

            # Populate Firms dynamically
            async def load_firms():
                firms = await ApiClient.fetch_available_firms()
                options = {f["firm_id"]: f"{f['firm_name']} ({f['firm_id']})" for f in firms}
                firm_select.options = options
                if options:
                    firm_select.value = list(options.keys())[0]

            ui.timer(0.05, load_firms, once=True)

            # User Credentials Fields
            full_name = ui.input("Full Name").classes("w-full").props("outlined dense")
            username = ui.input("Username").classes("w-full").props("outlined dense")
            email = ui.input("Email Address").classes("w-full").props("outlined dense type=email")
            phone = ui.input("Phone Number (Optional)").classes("w-full").props("outlined dense")
            password = ui.input("Default Password").classes("w-full").props("outlined dense type=password")

            error_label = ui.label("").classes("text-xs text-red-600 font-medium")

            # Submission Handler
            async def handle_create_user():
                error_label.set_text("")

                # Form Validation
                if not username.value or not email.value or not password.value or not full_name.value:
                    error_label.set_text("Please complete all required fields.")
                    return

                if role_select.value == "firm_admin" and not firm_select.value:
                    error_label.set_text("A Firm Admin must be assigned to an active firm.")
                    return

                payload = {
                    "username": username.value.strip(),
                    "email": email.value.strip(),
                    "password": password.value.strip(),
                    "full_name": full_name.value.strip(),
                    "phone": phone.value.strip() if phone.value else None,
                    "role": role_select.value,
                    "firm_id": firm_select.value if role_select.value == "firm_admin" else None,
                }

                submit_btn.props("loading")
                try:
                    await ApiClient.register_user(payload)
                    ui.notify(
                        f"User '{payload['username']}' registered successfully!",
                        color="positive",
                        position="top",
                    )
                    # Reset Form
                    full_name.value = ""
                    username.value = ""
                    email.value = ""
                    phone.value = ""
                    password.value = ""
                except Exception as ex:
                    error_label.set_text(str(ex))
                finally:
                    submit_btn.props(remove="loading")

            submit_btn = ui.button("Create Account", on_click=handle_create_user).classes(
                "w-full bg-blue-700 hover:bg-blue-800 text-white mt-2 py-2 font-semibold rounded-lg shadow-none"
            )