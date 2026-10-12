from datetime import date
from nicegui import ui
from client_app.session import AppSession, ApiClient

EXPENSE_CATEGORIES = {
    "LABOR": "Daily Labor & Wages",
    "FUEL_FIREWOOD": "Boiling Fuel & Firewood",
    "ELECTRICITY": "Electricity Bill",
    "WATER": "Water Supply Charges",
    "TRANSPORT": "Transport & Delivery",
    "REPAIR_MAINTENANCE": "Repairs & Maintenance",
    "RENT": "Shed / Land Rent",
    "MISC": "Miscellaneous",
}

PAYMENT_MODES = ["CASH", "UPI", "BANK_TRANSFER", "CREDIT"]


def render_expenses_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")
    expenses_list = []
    selected_filter = "ALL"

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        # Header
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Daily Charges & Labor Khata").classes("text-lg font-bold text-gray-800")
                    ui.label(f"Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )
            ui.button("Add Expense", icon="add", on_click=lambda: open_new_expense_dialog()).classes(
                "bg-orange-700 hover:bg-orange-800 text-white font-medium rounded-lg text-sm px-3 shadow-none"
            )

        # Metrics Summary Row
        summary_row = ui.row().classes("w-full gap-2 mb-3")

        # Category Filter Tabs
        filter_tabs = ui.row().classes("w-full gap-2 mb-2 overflow-x-auto pb-1")

        # List Container
        list_container = ui.column().classes("w-full gap-2")

        async def load_expenses():
            nonlocal expenses_list
            list_container.clear()
            with list_container:
                ui.spinner("dots").classes("self-center my-6 text-orange-700")

            expenses_list = await ApiClient.fetch_expenses_by_firm(target_firm_id)
            render_summary()
            render_filters()
            render_list()

        def render_summary():
            summary_row.clear()
            total_spent = sum(x["amount"] for x in expenses_list)
            labor_spent = sum(x["amount"] for x in expenses_list if x["category"] == "LABOR")

            with summary_row:
                with ui.card().classes("flex-1 p-3 border rounded-xl shadow-none bg-white"):
                    ui.label("Total Expenses").classes("text-xs text-gray-500 font-medium")
                    ui.label(f"₹{total_spent:,.2f}").classes("text-lg font-bold text-gray-800")
                with ui.card().classes("flex-1 p-3 border rounded-xl shadow-none bg-white"):
                    ui.label("Labor & Wages").classes("text-xs text-gray-500 font-medium")
                    ui.label(f"₹{labor_spent:,.2f}").classes("text-lg font-bold text-orange-700")

        def render_filters():
            filter_tabs.clear()
            filters = ["ALL", "LABOR", "FUEL_FIREWOOD", "TRANSPORT", "ELECTRICITY", "MISC"]
            with filter_tabs:
                for f in filters:
                    is_active = (f == selected_filter)
                    c_style = "bg-orange-700 text-white" if is_active else "bg-white text-gray-700 border"

                    def on_click(flt=f):
                        nonlocal selected_filter
                        selected_filter = flt
                        render_filters()
                        render_list()

                    label = "All Expenses" if f == "ALL" else EXPENSE_CATEGORIES.get(f, f)
                    ui.button(label, on_click=on_click).classes(
                        f"px-3 py-1 rounded-full text-xs font-semibold shadow-none {c_style}"
                    )

        def render_list():
            list_container.clear()
            filtered = (
                expenses_list
                if selected_filter == "ALL"
                else [x for x in expenses_list if x["category"] == selected_filter]
            )

            if not filtered:
                with list_container:
                    with ui.card().classes("w-full p-6 items-center justify-center border shadow-none bg-white rounded-xl"):
                        ui.icon("account_balance_wallet", size="3rem").classes("text-gray-300 mb-2")
                        ui.label("No expense records found").classes("text-sm text-gray-500")
                return

            with list_container:
                for item in filtered:
                    with ui.card().classes("w-full p-3.5 border rounded-xl shadow-none bg-white flex-row items-center justify-between"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("payments", size="1.75rem").classes("text-orange-700")
                            with ui.column().classes("gap-0 leading-tight"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(EXPENSE_CATEGORIES.get(item["category"], item["category"])).classes(
                                        "font-semibold text-gray-800 text-sm"
                                    )
                                    ui.badge(item["payment_mode"], color="grey-3", text_color="grey-9").props(
                                        "dense rounded text-xs"
                                    )
                                with ui.row().classes("items-center gap-2 text-xs text-gray-500 mt-1"):
                                    ui.label(f"Date: {item['expense_date']}")
                                    if item.get("paid_to"):
                                        ui.label(f"• Paid to: {item['paid_to']}")
                                    if item.get("remarks"):
                                        ui.label(f"• {item['remarks']}")

                        ui.label(f"₹{item['amount']:,.2f}").classes("text-base font-extrabold text-gray-900")

        # -------------------------------------------------------------
        # ADD EXPENSE DIALOG
        # -------------------------------------------------------------
        with ui.dialog() as add_dialog, ui.card().classes("w-full max-w-md p-6 rounded-xl"):
            ui.label("Record Daily Expense / Labor").classes("text-base font-bold text-gray-800 mb-2")

            exp_date = ui.input("Date *", value=date.today().isoformat()).classes("w-full").props("outlined dense type=date")
            cat_select = ui.select(EXPENSE_CATEGORIES, value="LABOR", label="Expense Category *").classes("w-full").props("outlined dense")
            amount_in = ui.number("Amount (₹) *", value=0.0, min=1.0).classes("w-full").props("outlined dense")
            paid_to_in = ui.input("Paid To (e.g. Laborer Name, Vendor)").classes("w-full").props("outlined dense")
            pay_mode = ui.select(PAYMENT_MODES, value="CASH", label="Payment Mode *").classes("w-full").props("outlined dense")
            remarks_in = ui.input("Remarks / Notes").classes("w-full").props("outlined dense")

            dialog_err = ui.label("").classes("text-xs text-red-600 font-medium")

            def open_new_expense_dialog():
                dialog_err.set_text("")
                add_dialog.open()

            async def submit_expense():
                dialog_err.set_text("")
                amt = float(amount_in.value or 0)
                if amt <= 0:
                    dialog_err.set_text("Please enter a valid amount greater than 0.")
                    return

                payload = {
                    "expense_date": exp_date.value,
                    "category": cat_select.value,
                    "amount": amt,
                    "paid_to": paid_to_in.value.strip() if paid_to_in.value else None,
                    "payment_mode": pay_mode.value,
                    "remarks": remarks_in.value.strip() if remarks_in.value else None,
                }

                save_btn.props("loading")
                try:
                    await ApiClient.record_expense(payload, firm_id=target_firm_id)
                    ui.notify("Expense recorded successfully!", color="positive", position="top")
                    add_dialog.close()
                    paid_to_in.value = ""
                    remarks_in.value = ""
                    amount_in.value = 0.0
                    await load_expenses()
                except Exception as ex:
                    dialog_err.set_text(str(ex))
                finally:
                    save_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=add_dialog.close).props("flat color=grey")
                save_btn = ui.button("Save Expense", on_click=submit_expense).classes("bg-orange-700 text-white rounded-lg")

        ui.timer(0.05, load_expenses, once=True)