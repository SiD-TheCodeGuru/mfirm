from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_stock_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No active firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")

    all_stocks = []
    selected_category = "All"
    firm_items_cache = {}

    with ui.column().classes("w-full max-w-5xl mx-auto p-4"):
        # Header
        with ui.row().classes("w-full items-center justify-between mb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Inventory & Stock Ledger").classes("text-xl font-bold text-gray-800")
                    ui.label(f"Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )
            ui.button("Adjust Stock", icon="tune", on_click=lambda: open_adjustment_dialog()).classes(
                "bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg text-sm px-3 shadow-none"
            )

        # Category Filter Tabs Container
        tabs_container = ui.row().classes("w-full gap-2 mb-3 overflow-x-auto pb-1")

        # Cards Container
        cards_container = ui.column().classes("w-full gap-2")

        async def load_stock_data():
            nonlocal all_stocks, firm_items_cache
            cards_container.clear()
            with cards_container:
                ui.spinner("dots").classes("self-center my-6 text-amber-600")

            # Load firm items for adjustment selection
            items = await ApiClient.fetch_items_by_firm(target_firm_id)
            firm_items_cache = {i["item_id"]: f"{i['item_name']} ({i['category']})" for i in items}

            all_stocks = await ApiClient.fetch_stock_by_firm(target_firm_id)
            render_category_tabs()
            render_stock_cards()

        def render_category_tabs():
            tabs_container.clear()
            categories = ["All"] + sorted(list({s["category"] for s in all_stocks if s.get("category")}))

            with tabs_container:
                for cat in categories:
                    is_active = (cat == selected_category)
                    btn_color = "bg-amber-600 text-white" if is_active else "bg-white text-gray-700 border"

                    def on_tab_click(c=cat):
                        nonlocal selected_category
                        selected_category = c
                        render_category_tabs()
                        render_stock_cards()

                    ui.button(cat, on_click=on_tab_click).classes(
                        f"px-3 py-1 rounded-full text-xs font-semibold shadow-none {btn_color}"
                    )

        def render_stock_cards():
            cards_container.clear()
            filtered = all_stocks if selected_category == "All" else [s for s in all_stocks if s.get("category") == selected_category]

            if not filtered:
                with cards_container:
                    with ui.card().classes("w-full p-8 items-center justify-center border shadow-none bg-white rounded-xl"):
                        ui.icon("inventory_2", size="3rem").classes("text-gray-300 mb-2")
                        ui.label(f"No stock items found for category '{selected_category}'").classes("text-sm text-gray-500")
                return

            with cards_container:
                for s in filtered:
                    # Category Badge Accent Color
                    cat_name = s.get("category", "General")
                    accent_colors = {
                        "Spawn": ("bg-emerald-50", "text-emerald-700", "border-emerald-200"),
                        "Raw Material": ("bg-amber-50", "text-amber-700", "border-amber-200"),
                        "Packaging": ("bg-blue-50", "text-blue-700", "border-blue-200"),
                        "Chemical / Fertilizer": ("bg-purple-50", "text-purple-700", "border-purple-200"),
                    }
                    bg_c, text_c, border_c = accent_colors.get(cat_name, ("bg-gray-50", "text-gray-700", "border-gray-200"))

                    with ui.card().classes("w-full p-4 border rounded-xl shadow-none bg-white flex-row items-center justify-between"):
                        with ui.row().classes("items-center gap-3"):
                            with ui.avatar().classes(f"{bg_c} {text_c} font-bold text-sm border {border_c}"):
                                ui.label(cat_name[:2].upper())

                            with ui.column().classes("gap-0 leading-tight"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(s["item_name"]).classes("font-bold text-gray-800 text-base")
                                    ui.badge(cat_name, color="grey-3", text_color="grey-9").props("dense rounded text-xs")

                                with ui.row().classes("items-center gap-3 text-xs text-gray-500 mt-1"):
                                    ui.label(f"Location: {s.get('warehouse_location') or 'Main Store'}")
                                    if s.get("remarks"):
                                        ui.label(f"• {s['remarks']}")

                        # Quantity Metric Display
                        with ui.column().classes("items-end gap-0"):
                            with ui.row().classes("items-baseline gap-1"):
                                ui.label(f"{s['quantity']:,.2f}").classes("text-xl font-black text-gray-900")
                                ui.label(s["unit"]).classes("text-xs font-semibold text-gray-500")
                            ui.label("In Stock").classes("text-xs text-emerald-600 font-bold")

        # -------------------------------------------------------------
        # STOCK ADJUSTMENT MODAL
        # -------------------------------------------------------------
        with ui.dialog() as adjust_dialog, ui.card().classes("w-full max-w-md p-6 rounded-xl"):
            ui.label("Manual Stock Adjustment").classes("text-base font-bold text-gray-800 mb-2")

            item_select = ui.select(
                options={},
                label="Select Item *",
            ).classes("w-full").props("outlined dense")

            with ui.row().classes("w-full gap-2"):
                adj_type = ui.select(
                    options={"add": "Add Stock (+)", "deduct": "Deduct / Spoilage (-)"},
                    value="add",
                    label="Action",
                ).classes("w-1/2").props("outlined dense")

                adj_qty = ui.number("Quantity *", value=1.0, min=0.01).classes("w-1/2").props("outlined dense")

            adj_location = ui.input("Warehouse Location", value="Main Store").classes("w-full").props("outlined dense")
            adj_remarks = ui.input("Adjustment Reason / Remarks").classes("w-full").props("outlined dense")
            dialog_err = ui.label("").classes("text-xs text-red-600 font-medium")

            def open_adjustment_dialog():
                item_select.options = firm_items_cache
                if firm_items_cache:
                    item_select.value = list(firm_items_cache.keys())[0]
                dialog_err.set_text("")
                adjust_dialog.open()

            async def submit_adjustment():
                dialog_err.set_text("")
                if not item_select.value:
                    dialog_err.set_text("Please choose an item.")
                    return

                qty = float(adj_qty.value or 0.0)
                delta = qty if adj_type.value == "add" else -qty

                payload = {
                    "item_id": item_select.value,
                    "quantity_delta": delta,
                    "warehouse_location": adj_location.value.strip() if adj_location.value else None,
                    "remarks": adj_remarks.value.strip() if adj_remarks.value else None,
                }

                save_adj_btn.props("loading")
                try:
                    await ApiClient.adjust_stock(payload, firm_id=target_firm_id)
                    ui.notify("Stock adjusted successfully!", color="positive", position="top")
                    adjust_dialog.close()
                    await load_stock_data()
                except Exception as ex:
                    dialog_err.set_text(str(ex))
                finally:
                    save_adj_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=adjust_dialog.close).props("flat color=grey")
                save_adj_btn = ui.button("Save", on_click=submit_adjustment).classes("bg-amber-600 text-white rounded-lg")

        ui.timer(0.05, load_stock_data, once=True)