from nicegui import ui
from client_app.session import ApiClient


def render_login_view():
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