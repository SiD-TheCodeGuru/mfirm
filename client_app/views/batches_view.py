from datetime import date
from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_batches_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No active firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    ui.query("body").classes("bg-gray-50")
    batches_list = []
    items_cache = {}

    with ui.column().classes("w-full max-w-5xl mx-auto p-4"):
        # Header Bar
        with ui.row().classes("w-full items-center justify-between mb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Batch & Flush Harvest Log").classes("text-xl font-bold text-gray-800")
                    ui.label(f"Firm Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )
            with ui.row().classes("gap-2"):
                ui.button("New Batch", icon="add", on_click=lambda: open_new_batch_dialog()).classes(
                    "bg-teal-700 hover:bg-teal-800 text-white font-medium rounded-lg text-sm px-3 shadow-none"
                )

        batches_container = ui.column().classes("w-full gap-3")

        # Data Loader
        async def load_data():
            nonlocal batches_list, items_cache
            batches_container.clear()
            with batches_container:
                ui.spinner("dots").classes("self-center my-6 text-teal-700")

            all_items = await ApiClient.fetch_items_by_firm(target_firm_id)
            items_cache = {
                i["item_id"]: f"{i['item_name']} ({i.get('category', 'Item')} - {i.get('default_unit', '')})"
                for i in all_items
            }

            batches_list = await ApiClient.fetch_batches_by_firm(target_firm_id)
            render_batches()

        def render_batches():
            batches_container.clear()
            if not batches_list:
                with batches_container:
                    with ui.card().classes(
                        "w-full p-8 items-center justify-center border shadow-none bg-white rounded-xl"
                    ):
                        ui.icon("spa", size="3rem").classes("text-gray-300 mb-2")
                        ui.label("No active cultivation batches found").classes("text-sm text-gray-500")
                return

            with batches_container:
                for b in batches_list:
                    status_colors = {
                        "INCUBATION": "blue",
                        "FRUITING": "green",
                        "COMPLETED": "grey",
                        "DISCARDED": "red",
                    }
                    badge_c = status_colors.get(b.get("status", "INCUBATION"), "teal")

                    with ui.card().classes("w-full p-4 border rounded-xl shadow-none bg-white"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(b["batch_code"]).classes("font-bold text-gray-800 text-lg")
                                ui.badge(b.get("status", "INCUBATION"), color=badge_c).props("dense rounded text-xs")
                                ui.label(f"• Room {b.get('room_no', 'N/A')}").classes("text-sm text-gray-500 font-medium")
                            with ui.row().classes("items-center gap-3"):
                                ui.button(
                                    "Log Flush Harvest",
                                    icon="scale",
                                    on_click=lambda bt=b: open_harvest_dialog(bt),
                                ).classes("bg-teal-700 text-white rounded-lg text-xs px-3 shadow-none")

                        # Key KPI metrics
                        with ui.row().classes("w-full gap-4 mt-3 bg-gray-50 p-3 rounded-lg border text-center"):
                            with ui.column().classes("flex-1 gap-0"):
                                ui.label("Bag Count").classes("text-xs text-gray-400 font-medium")
                                ui.label(f"{b.get('bag_count', 0)} Bags").classes("text-sm font-bold text-gray-700")

                            with ui.column().classes("flex-1 gap-0"):
                                ui.label("Dry Substrate").classes("text-xs text-gray-400 font-medium")
                                ui.label(f"{b.get('dry_substrate_weight_kg', 0.0):,.1f} kg").classes(
                                    "text-sm font-bold text-gray-700"
                                )

                            with ui.column().classes("flex-1 gap-0"):
                                ui.label("Harvested Yield").classes("text-xs text-gray-400 font-medium")
                                ui.label(f"{b.get('total_yield_kg', 0.0):,.2f} kg").classes(
                                    "text-sm font-extrabold text-teal-800"
                                )

                            with ui.column().classes("flex-1 gap-0"):
                                ui.label("Biological Efficiency").classes("text-xs text-gray-400 font-medium")
                                ui.label(f"{b.get('biological_efficiency') or 0.0:.1f} %").classes(
                                    "text-sm font-extrabold text-green-700"
                                )

                        # Consumed items summary
                        consumed = b.get("consumed_materials", [])
                        if consumed:
                            with ui.column().classes("w-full mt-2 pt-2 border-t text-xs text-gray-600 gap-1"):
                                ui.label("Materials Consumed:").classes("font-semibold text-gray-500 uppercase text-[10px]")
                                with ui.row().classes("gap-2 flex-wrap"):
                                    for mat in consumed:
                                        ui.badge(
                                            f"{mat['item_name']}: {mat['quantity']} {mat['unit']}",
                                            color="grey-3",
                                            text_color="grey-9",
                                        ).props("dense rounded text-xs")

                        with ui.row().classes("w-full justify-between items-center text-xs text-gray-400 mt-2"):
                            ui.label(f"Spawn Date: {b.get('spawn_date', '')}")
                            if b.get("remarks"):
                                ui.label(f"Remarks: {b['remarks']}")

        # -------------------------------------------------------------
        # 1. NEW BATCH MODAL (Lists all stock items with input quantities)
        # -------------------------------------------------------------
        stock_inputs_map = {}  # {item_id: ui.number input reference}

        with ui.dialog().classes("w-full") as new_batch_dialog, ui.card().classes("w-full max-w-2xl p-6 rounded-xl"):
            ui.label("Register New Mushroom Batch").classes("text-lg font-bold text-gray-800 mb-2")

            with ui.row().classes("w-full gap-2"):
                b_code = ui.input("Batch Code *", placeholder="e.g. OYST-2026-B1").classes("w-1/2").props("outlined dense")
                b_date = ui.input("Spawning Date *", value=date.today().isoformat()).classes("w-1/2").props(
                    "outlined dense type=date"
                )

            with ui.row().classes("w-full gap-2"):
                b_room = ui.input("Cropping Room / Shed *", placeholder="e.g. Room-2").classes("w-1/3").props(
                    "outlined dense"
                )
                b_bags = ui.number("Total Bags *", value=200, min=1).classes("w-1/3").props("outlined dense")
                b_dry_wt = ui.number("Dry Substrate Wt (kg) *", value=200.0, min=1.0).classes("w-1/3").props("outlined dense")

            b_remarks = ui.input("Remarks (Optional)").classes("w-full").props("outlined dense")

            ui.separator().classes("my-2")
            ui.label("Select Materials Used From Stock").classes(
                "text-xs font-bold text-gray-500 uppercase tracking-wider mb-1"
            )

            stock_table_box = ui.column().classes("w-full max-h-60 overflow-y-auto border rounded-lg p-2 bg-gray-50 gap-2")
            b_err = ui.label("").classes("text-xs text-red-600 font-medium")

            async def open_new_batch_dialog():
                b_err.set_text("")
                stock_inputs_map.clear()
                stock_table_box.clear()

                with stock_table_box:
                    ui.spinner("dots").classes("self-center my-3 text-teal-700")

                new_batch_dialog.open()

                # Fetch all stock records for this firm
                firm_stocks = await ApiClient.fetch_stock_by_firm(target_firm_id)
                stock_table_box.clear()

                if not firm_stocks:
                    with stock_table_box:
                        ui.label("No stock records found for this firm. Record purchases or adjust stock first.").classes(
                            "text-xs text-amber-700 italic p-2"
                        )
                    return

                with stock_table_box:
                    for s in firm_stocks:
                        avail = float(s.get("quantity", 0.0))
                        item_id = s["item_id"]
                        unit = s.get("unit", "kg")
                        cat = s.get("category", "General")

                        with ui.row().classes("w-full items-center justify-between border-b pb-1.5 pt-1 bg-white px-2 rounded"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(s["item_name"]).classes("text-sm font-semibold text-gray-800")
                                ui.badge(cat, color="grey-3", text_color="grey-9").props("dense rounded text-[10px]")
                                ui.label(f"(Avail: {avail:,.2f} {unit})").classes("text-xs text-gray-500 font-medium")

                            # Number input for quantity used
                            qty_input = ui.number(
                                label=f"Used ({unit})",
                                value=0.0,
                                min=0.0,
                                max=avail,
                            ).classes("w-32").props("outlined dense")

                            stock_inputs_map[item_id] = {
                                "input": qty_input,
                                "available": avail,
                                "name": s["item_name"],
                                "unit": unit,
                            }

            async def submit_batch():
                b_err.set_text("")
                if not b_code.value or not b_room.value:
                    b_err.set_text("Batch code and cropping room are required.")
                    return

                # Build consumed materials list
                consumed_list = []
                for itm_id, obj in stock_inputs_map.items():
                    val = float(obj["input"].value or 0.0)
                    if val > 0:
                        if val > obj["available"]:
                            b_err.set_text(
                                f"Cannot use {val} {obj['unit']} for '{obj['name']}'. Only {obj['available']} available."
                            )
                            return
                        consumed_list.append({"item_id": itm_id, "quantity": val})

                payload = {
                    "batch_code": b_code.value.strip(),
                    "spawn_date": b_date.value,
                    "room_no": b_room.value.strip(),
                    "bag_count": int(b_bags.value or 1),
                    "dry_substrate_weight_kg": float(b_dry_wt.value or 1.0),
                    "consumed_materials": consumed_list,
                    "remarks": b_remarks.value.strip() if b_remarks.value else None,
                }

                save_batch_btn.props("loading")
                try:
                    await ApiClient.create_batch(payload, firm_id=target_firm_id)
                    ui.notify("Batch created and all stock items deducted!", color="positive", position="top")
                    new_batch_dialog.close()
                    b_code.value = ""
                    b_room.value = ""
                    b_remarks.value = ""
                    await load_data()
                except Exception as ex:
                    b_err.set_text(str(ex))
                finally:
                    save_batch_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=new_batch_dialog.close).props("flat color=grey")
                save_batch_btn = ui.button("Create Batch & Deduct Stock", on_click=submit_batch).classes(
                    "bg-teal-700 text-white rounded-lg shadow-none"
                )

        # -------------------------------------------------------------
        # 2. LOG DAILY FLUSH HARVEST MODAL
        # -------------------------------------------------------------
        active_batch_ctx = None
        with ui.dialog() as harvest_dialog, ui.card().classes("w-full max-w-md p-6 rounded-xl"):
            harvest_title = ui.label("Record Flush Harvest").classes("text-base font-bold text-gray-800 mb-2")

            h_date = ui.input("Harvest Date *", value=date.today().isoformat()).classes("w-full").props(
                "outlined dense type=date"
            )

            with ui.row().classes("w-full gap-2"):
                h_flush = ui.select(
                    options={1: "Flush 1 (Primary)", 2: "Flush 2 (Secondary)", 3: "Flush 3 (Final)"},
                    value=1,
                    label="Flush Wave *",
                ).classes("w-1/2").props("outlined dense")
                h_grade = ui.select(
                    options={"A_GRADE": "Grade A", "B_GRADE": "Grade B", "COMMERCIAL": "Commercial"},
                    value="A_GRADE",
                    label="Mushroom Grade",
                ).classes("w-1/2").props("outlined dense")

            h_weight = ui.number("Picked Weight (kg) *", value=10.0, min=0.1).classes("w-full").props("outlined dense")
            h_fresh_item = ui.select(
                options={},
                label="Add into Fresh Mushroom Stock Item",
            ).classes("w-full").props("outlined dense clearable")
            h_notes = ui.input("Remarks (e.g. Pinhead quality, humidity)").classes("w-full").props("outlined dense")
            h_err = ui.label("").classes("text-xs text-red-600 font-medium")

            async def open_harvest_dialog(batch_data):
                nonlocal active_batch_ctx
                active_batch_ctx = batch_data
                harvest_title.set_text(f"Record Harvest — {batch_data['batch_code']}")

                # Populate item options
                all_items = await ApiClient.fetch_items_by_firm(target_firm_id)
                fresh_options = {
                    i["item_id"]: f"{i['item_name']} ({i.get('category', 'Item')} - {i.get('default_unit', '')})"
                    for i in all_items
                }
                h_fresh_item.set_options(fresh_options)
                h_fresh_item.value = None
                h_fresh_item.update()

                h_err.set_text("")
                harvest_dialog.open()

            async def submit_harvest():
                h_err.set_text("")
                if not h_weight.value or float(h_weight.value) <= 0:
                    h_err.set_text("Valid harvested weight is required.")
                    return

                payload = {
                    "batch_id": active_batch_ctx["batch_id"],
                    "harvest_date": h_date.value,
                    "flush_number": int(h_flush.value),
                    "weight_kg": float(h_weight.value),
                    "grade": h_grade.value,
                    "harvested_item_id": h_fresh_item.value if h_fresh_item.value else None,
                    "remarks": h_notes.value.strip() if h_notes.value else None,
                }

                save_hrv_btn.props("loading")
                try:
                    await ApiClient.log_harvest(payload, firm_id=target_firm_id)
                    ui.notify("Harvest logged and fresh stock updated!", color="positive", position="top")
                    harvest_dialog.close()
                    h_notes.value = ""
                    await load_data()
                except Exception as ex:
                    h_err.set_text(str(ex))
                finally:
                    save_hrv_btn.props(remove="loading")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=harvest_dialog.close).props("flat color=grey")
                save_hrv_btn = ui.button("Save Harvest", on_click=submit_harvest).classes(
                    "bg-teal-700 text-white rounded-lg shadow-none"
                )

        ui.timer(0.05, load_data, once=True)