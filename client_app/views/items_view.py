from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_items_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No active firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")

    all_items = []

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        # Top Header Bar
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Item Master Catalog").classes("text-lg font-bold text-gray-800")
                    ui.label(f"Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )
            ui.button("Add Item", icon="add", on_click=lambda: add_dialog.open()).classes(
                "bg-green-700 hover:bg-green-800 text-white font-medium rounded-lg text-sm px-3 shadow-none"
            )

        # Search Bar
        search_input = ui.input(placeholder="Search by item name or category...").classes(
            "w-full bg-white mb-3"
        ).props("outlined dense clearable prepend-icon=search")

        # Items Table / List Container
        items_container = ui.column().classes("w-full gap-2")

        # Refresh List Handler
        async def load_items():
            nonlocal all_items
            items_container.clear()
            with items_container:
                ui.spinner("dots").classes("self-center my-6 text-green-700")

            all_items = await ApiClient.fetch_items_by_firm(target_firm_id)
            render_filtered_items()

        def render_filtered_items():
            items_container.clear()
            filter_query = (search_input.value or "").strip().lower()

            filtered = [
                i for i in all_items
                if filter_query in i["item_name"].lower() or filter_query in i["category"].lower()
            ]

            if not filtered:
                with items_container:
                    with ui.card().classes("w-full p-6 items-center justify-center border shadow-none bg-white"):
                        ui.icon("inventory_2", size="3rem").classes("text-gray-300 mb-2")
                        ui.label("No items found").classes("text-sm text-gray-500")
                return

            with items_container:
                for item in filtered:
                    with ui.card().classes(
                        "w-full p-3.5 border rounded-xl shadow-none bg-white flex-row items-center justify-between hover:bg-gray-50 transition-colors"
                    ):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("category", size="1.75rem").classes("text-green-700")
                            with ui.column().classes("gap-0 leading-tight"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(item["item_name"]).classes("font-semibold text-gray-800 text-sm")
                                    ui.badge(item["category"], color="blue-grey-2", text_color="blue-grey-9").props(
                                        "dense rounded text-xs"
                                    )
                                with ui.row().classes("items-center gap-2 text-xs text-gray-500 mt-0.5"):
                                    ui.label(f"Default Unit: {item['default_unit']}")
                                    if item.get("remarks"):
                                        ui.label(f"• {item['remarks']}")

                        ui.button(
                            icon="edit",
                            on_click=lambda it=item: open_edit_dialog(it),
                        ).props("flat round dense color=primary")

        search_input.on_value_change(render_filtered_items)

        # -------------------------------------------------------------
        # ADD ITEM DIALOG
        # -------------------------------------------------------------
        with ui.dialog() as add_dialog, ui.card().classes("w-full max-w-md p-6 rounded-xl"):
            ui.label("Register New Item").classes("text-base font-bold text-gray-800 mb-2")
            add_name = ui.input("Item Name *").classes("w-full").props("outlined dense")
            add_category = ui.select(
                options=["Spawn", "Raw Material", "Packaging", "Chemical / Fertilizer", "Consumable", "Equipment"],
                label="Category *",
            ).classes("w-full").props("outlined dense")
            add_unit = ui.select(
                # Allowed units in add_dialog and edit_dialog:
                options=["kg", "packets", "bags", "bottles", "pieces", "ltr"],
                label="Default Unit *",
            ).classes("w-full").props("outlined dense")
            add_remarks = ui.input("Remarks (Optional)").classes("w-full").props("outlined dense")
            add_error = ui.label("").classes("text-xs text-red-600 font-medium")

            async def submit_add():
                add_error.set_text("")
                if not add_name.value or not add_category.value or not add_unit.value:
                    add_error.set_text("Name, Category, and Unit are required.")
                    return

                payload = {
                    "item_name": add_name.value.strip(),
                    "category": add_category.value.strip(),
                    "default_unit": add_unit.value.strip(),
                    "remarks": add_remarks.value.strip() if add_remarks.value else None,
                }
                add_btn.props("loading")
                try:
                    await ApiClient.create_item(payload, firm_id=target_firm_id)
                    ui.notify("Item registered successfully!", color="positive", position="top")
                    add_dialog.close()
                    add_name.value = ""
                    add_remarks.value = ""
                    await load_items()
                except Exception as ex:
                    add_error.set_text(str(ex))
                finally:
                    add_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=add_dialog.close).props("flat color=grey")
                add_btn = ui.button("Save Item", on_click=submit_add).classes("bg-green-700 text-white rounded-lg")

        # -------------------------------------------------------------
        # EDIT ITEM DIALOG
        # -------------------------------------------------------------
        selected_item_id = None
        with ui.dialog() as edit_dialog, ui.card().classes("w-full max-w-md p-6 rounded-xl"):
            ui.label("Edit Item").classes("text-base font-bold text-gray-800 mb-2")
            edit_name = ui.input("Item Name").classes("w-full").props("outlined dense")
            edit_category = ui.select(
                options=["Spawn", "Raw Material", "Packaging", "Chemical / Fertilizer", "Consumable", "Equipment"],
                label="Category",
            ).classes("w-full").props("outlined dense")
            edit_unit = ui.select(
                # Allowed units in add_dialog and edit_dialog:
                options=["kg", "packets", "bags", "bottles", "pieces", "ltr"],
                label="Default Unit",
            ).classes("w-full").props("outlined dense")
            edit_remarks = ui.input("Remarks").classes("w-full").props("outlined dense")
            edit_error = ui.label("").classes("text-xs text-red-600 font-medium")

            def open_edit_dialog(item_data):
                nonlocal selected_item_id
                selected_item_id = item_data["item_id"]
                edit_name.value = item_data["item_name"]
                edit_category.value = item_data["category"]
                edit_unit.value = item_data["default_unit"]
                edit_remarks.value = item_data.get("remarks") or ""
                edit_error.set_text("")
                edit_dialog.open()

            async def submit_edit():
                edit_error.set_text("")
                payload = {
                    "item_name": edit_name.value.strip() if edit_name.value else None,
                    "category": edit_category.value.strip() if edit_category.value else None,
                    "default_unit": edit_unit.value.strip() if edit_unit.value else None,
                    "remarks": edit_remarks.value.strip() if edit_remarks.value else None,
                }
                edit_btn.props("loading")
                try:
                    await ApiClient.update_item(selected_item_id, payload)
                    ui.notify("Item updated successfully!", color="positive", position="top")
                    edit_dialog.close()
                    await load_items()
                except Exception as ex:
                    edit_error.set_text(str(ex))
                finally:
                    edit_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=edit_dialog.close).props("flat color=grey")
                edit_btn = ui.button("Update", on_click=submit_edit).classes("bg-blue-700 text-white rounded-lg")

        ui.timer(0.05, load_items, once=True)