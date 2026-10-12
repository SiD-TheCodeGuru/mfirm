from datetime import date
from nicegui import ui
from client_app.session import AppSession, ApiClient

VALID_UNITS = ["kg", "packets", "bags", "bottles", "pieces", "ltr"]
PAYMENT_MODES = ["CASH", "BANK_TRANSFER", "UPI", "CREDIT"]


def render_purchases_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No active firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")
    purchases_list = []
    firm_items_cache = {}

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        # Header
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Purchases & Invoices").classes("text-lg font-bold text-gray-800")
                    ui.label(f"Firm Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )
            ui.button("New Invoice", icon="add", on_click=lambda: open_new_purchase_dialog()).classes(
                "bg-green-700 hover:bg-green-800 text-white font-medium rounded-lg text-sm px-3 shadow-none"
            )

        list_container = ui.column().classes("w-full gap-2")

        async def load_data():
            nonlocal purchases_list, firm_items_cache
            list_container.clear()
            with list_container:
                ui.spinner("dots").classes("self-center my-6 text-green-700")

            # Pre-load item catalog for dropdowns
            items = await ApiClient.fetch_items_by_firm(target_firm_id)
            firm_items_cache = {i["item_id"]: f"{i['item_name']} ({i['default_unit']})" for i in items}

            purchases_list = await ApiClient.fetch_purchases_by_firm(target_firm_id)
            render_purchases()

        def render_purchases():
            list_container.clear()
            if not purchases_list:
                with list_container:
                    with ui.card().classes("w-full p-6 items-center justify-center border shadow-none bg-white rounded-xl"):
                        ui.icon("receipt_long", size="3rem").classes("text-gray-300 mb-2")
                        ui.label("No purchases recorded yet").classes("text-sm text-gray-500")
                return

            with list_container:
                for pur in purchases_list:
                    with ui.card().classes("w-full p-4 border rounded-xl shadow-none bg-white mb-1"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(f"#{pur['slno']}").classes("text-xs font-bold text-gray-400")
                                ui.label(pur["invoice_no"]).classes("font-bold text-gray-800 text-base")
                                ui.badge(pur["payment_mode"], color="teal-2", text_color="teal-9").props("dense rounded text-xs")
                            with ui.column().classes("items-end gap-0"):
                                ui.label(f"₹{pur['total_paid']:,.2f}").classes("text-base font-extrabold text-green-800")
                                ui.label(f"Date: {pur['invoice_date']}").classes("text-xs text-gray-400")

                        with ui.row().classes("w-full items-center justify-between text-xs text-gray-500 mt-2 border-t pt-2"):
                            ui.label(f"Vendor: {pur.get('vendor_name') or 'N/A'}")
                            ui.label(f"Tax: ₹{pur.get('tax_paid', 0):,.2f}")
                            ui.label(f"Items: {len(pur.get('items', []))}")

        # -------------------------------------------------------------
        # MODAL: Record New Invoice
        # -------------------------------------------------------------
        line_items_state = []

        with ui.dialog().classes("w-full") as new_dialog, ui.card().classes("w-full max-w-2xl p-6 rounded-xl"):
            ui.label("Record Purchase Invoice").classes("text-base font-bold text-gray-800 mb-2")

            with ui.row().classes("w-full gap-2"):
                inv_no = ui.input("Invoice No *").classes("w-1/2").props("outlined dense")
                inv_date = ui.input("Invoice Date *", value=date.today().isoformat()).classes("w-1/2").props("outlined dense type=date")

            with ui.row().classes("w-full gap-2"):
                vendor = ui.input("Vendor Name").classes("w-1/2").props("outlined dense")
                pay_mode = ui.select(PAYMENT_MODES, value="UPI", label="Payment Mode *").classes("w-1/2").props("outlined dense")

            with ui.row().classes("w-full gap-2"):
                tax = ui.number("Tax Paid (₹)", value=0.0, min=0.0).classes("w-1/2").props("outlined dense")
                total = ui.number("Total Amount (₹) *", value=0.0, min=0.0).classes("w-1/2").props("outlined dense")

            inv_remarks = ui.input("Remarks (Optional)").classes("w-full").props("outlined dense")

            ui.separator().classes("my-2")
            ui.label("Line Items *").classes("text-xs font-bold text-gray-500 uppercase tracking-wider")

            items_box = ui.column().classes("w-full gap-2")

            def add_line_item_row():
                row_state = {
                    "item_id": list(firm_items_cache.keys())[0] if firm_items_cache else "",
                    "quantity": 1.0,
                    "unit": "kg",
                    "purchage_amt": 0.0,
                    "remarks": None,
                }
                line_items_state.append(row_state)
                render_line_item_rows()

            def remove_line_item_row(index: int):
                if len(line_items_state) > 1:
                    line_items_state.pop(index)
                    render_line_item_rows()

            def render_line_item_rows():
                items_box.clear()
                with items_box:
                    for idx, row in enumerate(line_items_state):
                        with ui.row().classes("w-full items-center gap-2 border p-2 rounded-lg bg-gray-50"):
                            item_sel = ui.select(
                                options=firm_items_cache,
                                value=row["item_id"],
                                label="Item",
                            ).classes("w-44").props("outlined dense")
                            item_sel.on_value_change(lambda e, r=row: r.update({"item_id": e.value}))

                            qty_in = ui.number("Qty", value=row["quantity"], min=0.01).classes("w-20").props("outlined dense")
                            qty_in.on_value_change(lambda e, r=row: r.update({"quantity": float(e.value or 0)}))

                            unit_sel = ui.select(VALID_UNITS, value=row["unit"], label="Unit").classes("w-24").props("outlined dense")
                            unit_sel.on_value_change(lambda e, r=row: r.update({"unit": e.value}))

                            amt_in = ui.number("Cost (₹)", value=row["purchage_amt"], min=0.0).classes("w-24").props("outlined dense")

                            def update_amt(e, r=row):
                                r.update({"purchage_amt": float(e.value or 0)})
                                auto_sum = sum(x["purchage_amt"] for x in line_items_state) + float(tax.value or 0)
                                total.value = auto_sum

                            amt_in.on_value_change(update_amt)

                            if len(line_items_state) > 1:
                                ui.button(icon="delete", on_click=lambda _, i=idx: remove_line_item_row(i)).props("flat round dense color=negative")

                ui.button("Add Item Row", icon="add", on_click=add_line_item_row).props("flat dense color=primary")

            dialog_err = ui.label("").classes("text-xs text-red-600 font-medium")

            def open_new_purchase_dialog():
                if not firm_items_cache:
                    ui.notify("Please register at least one item in the Item Catalog first.", color="warning")
                    return
                line_items_state.clear()
                add_line_item_row()
                dialog_err.set_text("")
                new_dialog.open()

            async def submit_purchase():
                dialog_err.set_text("")
                if not inv_no.value or not inv_date.value:
                    dialog_err.set_text("Invoice Number and Date are required.")
                    return

                if not line_items_state:
                    dialog_err.set_text("At least one line item is required.")
                    return

                payload = {
                    "invoice_no": inv_no.value.strip(),
                    "invoice_date": inv_date.value,
                    "vendor_name": vendor.value.strip() if vendor.value else None,
                    "payment_mode": pay_mode.value,
                    "tax_paid": float(tax.value or 0.0),
                    "total_paid": float(total.value or 0.0),
                    "remarks": inv_remarks.value.strip() if inv_remarks.value else None,
                    "items": line_items_state,
                }

                save_btn.props("loading")
                try:
                    await ApiClient.record_purchase(payload, firm_id=target_firm_id)
                    ui.notify("Purchase recorded and stock ledger updated!", color="positive", position="top")
                    new_dialog.close()
                    inv_no.value = ""
                    vendor.value = ""
                    inv_remarks.value = ""
                    await load_data()
                except Exception as ex:
                    dialog_err.set_text(str(ex))
                finally:
                    save_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=new_dialog.close).props("flat color=grey")
                save_btn = ui.button("Save Invoice", on_click=submit_purchase).classes("bg-green-700 text-white rounded-lg")

        ui.timer(0.05, load_data, once=True)