from datetime import date
import json
from nicegui import ui
from client_app.session import AppSession, ApiClient


def render_reports_view():
    if not AppSession.is_logged_in():
        ui.navigate.to("/login")
        return

    target_firm_id = AppSession.active_firm_id
    if not target_firm_id:
        ui.notify("No active firm context selected.", color="warning")
        ui.navigate.to("/dashboard")
        return

    # Injected jsPDF + jspdf-autotable library for multi-page tabular PDF export
    ui.add_head_html("""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
    <script>
      window.exportTabularReportPDF = function(config) {
        try {
          const { jsPDF } = window.jspdf;
          const doc = new jsPDF({
            orientation: config.orientation || 'portrait',
            unit: 'pt',
            format: 'a4'
          });

          const title = config.title || "Report";
          const firmName = config.firmName || "Mushroom Farm Unit";
          const now = new Date();
          const printDateTime = now.toLocaleDateString() + " " + now.toLocaleTimeString();

          let startY = 80;

          // 1. Snapshot ECharts canvas if element ID provided
          if (config.containerId) {
            const container = document.getElementById(config.containerId);
            if (container) {
              const canvas = container.querySelector('canvas');
              if (canvas) {
                const exportCanvas = document.createElement('canvas');
                exportCanvas.width = canvas.width;
                exportCanvas.height = canvas.height;
                const ctx = exportCanvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
                ctx.drawImage(canvas, 0, 0);

                const imgData = exportCanvas.toDataURL('image/png', 1.0);
                const pageWidth = doc.internal.pageSize.getWidth();
                const margin = 40;
                const maxW = pageWidth - (margin * 2);
                const renderH = (exportCanvas.height * maxW) / exportCanvas.width;

                doc.addImage(imgData, 'PNG', margin, 85, maxW, Math.min(renderH, 240));
                startY = 85 + Math.min(renderH, 240) + 20;
              }
            }
          }

          // 2. Generate Multi-Page Tabular Document with auto-repeating headers
          doc.autoTable({
            startY: startY,
            head: [config.columns],
            body: config.rows,
            theme: 'striped',
            styles: {
              fontSize: 9,
              cellPadding: 6,
              textColor: [30, 41, 59],
              valign: 'middle'
            },
            headStyles: {
              fillColor: [15, 23, 42],
              textColor: [255, 255, 255],
              fontStyle: 'bold',
              halign: 'left'
            },
            alternateRowStyles: {
              fillColor: [248, 250, 252]
            },
            margin: { top: 75, bottom: 50, left: 40, right: 40 },
            showHead: 'everyPage',

            // Running header and footer hook drawn on every page
            didDrawPage: function(data) {
              const pageWidth = doc.internal.pageSize.getWidth();
              const pageHeight = doc.internal.pageSize.getHeight();

              // Top Header
              doc.setFontSize(14);
              doc.setFont(undefined, 'bold');
              doc.setTextColor(15, 23, 42);
              doc.text(title, 40, 35);

              doc.setFontSize(9);
              doc.setFont(undefined, 'normal');
              doc.setTextColor(100, 116, 139);
              doc.text("Firm: " + firmName, 40, 50);

              // Top Right Date-Time & Subtitle
              doc.text("Generated: " + printDateTime, pageWidth - 40, 35, { align: 'right' });
              if (config.subtitle) {
                doc.text(config.subtitle, pageWidth - 40, 50, { align: 'right' });
              }

              // Header divider
              doc.setDrawColor(226, 232, 240);
              doc.setLineWidth(1);
              doc.line(40, 60, pageWidth - 40, 60);

              // Footer rule
              doc.setDrawColor(226, 232, 240);
              doc.line(40, pageHeight - 35, pageWidth - 40, pageHeight - 35);

              doc.setFontSize(8);
              doc.setTextColor(148, 163, 184);
              doc.text("Mushroom Farm ERP Ledger — Official Record", 40, pageHeight - 20);
            }
          });

          // 3. Two-pass page numbering: Page X of Y
          const pageCount = doc.internal.getNumberOfPages();
          for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(148, 163, 184);
            const pageWidth = doc.internal.pageSize.getWidth();
            const pageHeight = doc.internal.pageSize.getHeight();
            doc.text("Page " + i + " of " + pageCount, pageWidth - 40, pageHeight - 20, { align: 'right' });
          }

          doc.save(title.replace(/\\s+/g, '_') + '.pdf');
        } catch (err) {
          console.error("PDF Export error:", err);
          alert("Failed to export PDF: " + err.message);
        }
      };
    </script>
    """)

    ui.query("body").classes("bg-gray-50")

    # Filter state
    current_year = date.today().year
    filter_state = {
        "year": current_year,
        "start_date": None,
        "end_date": None,
        "batch_id": "ALL",
    }
    batch_options = {"ALL": "All Batches"}

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        # Header Bar
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("flat round color=primary")
                with ui.column().classes("gap-0"):
                    ui.label("Farm Analytics & Reports").classes("text-xl font-black text-gray-800")
                    ui.label(f"Context: {AppSession.active_firm_name or target_firm_id}").classes(
                        "text-xs text-gray-500 font-medium"
                    )

        # -------------------------------------------------------------
        # FILTER TOOLBAR (Year, Date Range, Batch Select)
        # -------------------------------------------------------------
        with ui.card().classes("w-full p-4 border rounded-xl shadow-none bg-white mb-3"):
            ui.label("Filter Reports").classes("text-xs font-bold text-gray-400 uppercase tracking-wider mb-1")
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                year_sel = ui.select(
                    options=[current_year - 1, current_year, current_year + 1],
                    value=filter_state["year"],
                    label="Harvest Year",
                ).classes("w-32").props("outlined dense")

                start_in = ui.input(label="Start Date").classes("w-36").props("outlined dense type=date")
                end_in = ui.input(label="End Date").classes("w-36").props("outlined dense type=date")

                batch_sel = ui.select(
                    options=batch_options,
                    value="ALL",
                    label="Batch Selection",
                ).classes("w-52").props("outlined dense")

                async def apply_filters():
                    filter_state["year"] = year_sel.value
                    filter_state["start_date"] = start_in.value if start_in.value else None
                    filter_state["end_date"] = end_in.value if end_in.value else None
                    filter_state["batch_id"] = batch_sel.value
                    await load_and_render_reports()

                async def reset_filters():
                    year_sel.value = current_year
                    start_in.value = None
                    end_in.value = None
                    batch_sel.value = "ALL"
                    await apply_filters()

                with ui.row().classes("gap-2 items-center"):
                    ui.button("Filter", icon="filter_alt", on_click=apply_filters).classes(
                        "bg-indigo-700 text-white rounded-lg text-xs px-3 shadow-none"
                    )
                    ui.button("Reset", icon="restart_alt", on_click=reset_filters).props("flat text-color=grey text-xs")

        content_box = ui.column().classes("w-full gap-4")

        async def load_and_render_reports():
            content_box.clear()
            with content_box:
                ui.spinner("dots").classes("self-center my-8 text-indigo-700")

            # Refresh batch options in dropdown
            batches_list = await ApiClient.fetch_batches_by_firm(target_firm_id)
            for b in batches_list:
                batch_options[b["batch_id"]] = f"{b['batch_code']} ({b.get('room_no', '')})"
            batch_sel.set_options(batch_options)

            data = await ApiClient.fetch_farm_reports(
                firm_id=target_firm_id,
                start_date=filter_state["start_date"],
                end_date=filter_state["end_date"],
                year=filter_state["year"],
                batch_id=filter_state["batch_id"],
            )

            content_box.clear()

            if not data or not data.get("kpis"):
                with content_box:
                    with ui.card().classes("w-full p-8 items-center justify-center border shadow-none bg-white rounded-xl"):
                        ui.icon("bar_chart", size="3rem").classes("text-gray-300 mb-2")
                        ui.label("No data available for the chosen filters.").classes("text-sm text-gray-500")
                return

            kpis = data["kpis"]

            with content_box:
                # -------------------------------------------------------------
                # ROW 1: EXECUTIVE KPI SUMMARY TILES
                # -------------------------------------------------------------
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    def kpi_card(title: str, value: str, sub: str, icon: str, color_theme: str):
                        with ui.card().classes("flex-1 min-w-[200px] p-4 border rounded-xl shadow-none bg-white"):
                            with ui.row().classes("items-center justify-between"):
                                ui.label(title).classes("text-xs font-bold text-gray-400 uppercase tracking-wider")
                                ui.icon(icon, size="1.5rem").classes(color_theme)
                            ui.label(value).classes("text-2xl font-black text-gray-900 mt-1")
                            ui.label(sub).classes("text-xs text-gray-500 mt-0.5")

                    kpi_card("Total Production", f"{kpis['total_yield_kg']:,.1f} kg", f"{kpis['total_bags_spawned']} Bags Inoculated", "spa", "text-emerald-600")
                    kpi_card("Avg Biological Efficiency", f"{kpis['average_be_percent']:.1f} %", "Target: 80% - 120%", "speed", "text-teal-600")
                    kpi_card("Operating Expenses", f"₹{kpis['total_expenses']:,.2f}", "Wages, Fuel & Utilities", "receipt_long", "text-amber-600")
                    kpi_card("Production Cost / Kg", f"₹{kpis['cost_per_kg']:,.2f}", "Combined Material + Labor", "savings", "text-indigo-600")

                # -------------------------------------------------------------
                # ROW 2: HARVEST TIMELINE & FLUSH DISTRIBUTION
                # -------------------------------------------------------------
                with ui.row().classes("w-full gap-4"):
                    # 1. Daily Harvest Curve Card
                    timeline = data.get("daily_timeline", [])
                    harvest_table_rows = [
                        [d["date"], f"{d['weight']:.2f} kg", "Logged Daily Picking"]
                        for d in timeline
                    ]

                    def export_harvest_pdf():
                        cfg = {
                            "title": "Daily Harvest Yield Report",
                            "firmName": AppSession.active_firm_name or target_firm_id,
                            "subtitle": f"Period: {filter_state['start_date'] or 'Start'} to {filter_state['end_date'] or 'Present'}",
                            "containerId": "chart_box_1",
                            "orientation": "portrait",
                            "columns": ["Picking Date", "Harvested Yield (Kg)", "Session Notes"],
                            "rows": harvest_table_rows,
                        }
                        ui.run_javascript(f"window.exportTabularReportPDF({json.dumps(cfg)});")

                    with ui.card().classes("flex-2 min-w-[340px] flex-1 p-4 border rounded-xl shadow-none bg-white"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            ui.label("Daily Harvest Yield Trend (Kg)").classes("text-sm font-bold text-gray-800")
                            ui.button("PDF", icon="picture_as_pdf", on_click=export_harvest_pdf).classes(
                                "bg-emerald-700 text-white rounded-lg text-xs px-2.5 py-1 shadow-none"
                            )

                        dates = [d["date"] for d in timeline]
                        weights = [d["weight"] for d in timeline]

                        with ui.element('div').props('id="chart_box_1"').classes("w-full h-64"):
                            ui.echart({
                                "tooltip": {"trigger": "axis"},
                                "xAxis": {"type": "category", "data": dates, "axisLabel": {"rotate": 30, "fontSize": 10}},
                                "yAxis": {"type": "value", "name": "Kg"},
                                "series": [{
                                    "data": weights,
                                    "type": "line",
                                    "smooth": True,
                                    "color": "#059669",
                                    "areaStyle": {"color": "rgba(16, 185, 129, 0.15)"},
                                }],
                                "grid": {"left": "10%", "right": "5%", "bottom": "18%", "top": "15%"},
                            }).classes("w-full h-full")

                    # 2. Flush Distribution Card
                    flush_dict = data.get("flush_distribution", {})
                    flush_total = sum(flush_dict.values())
                    flush_table_rows = [
                        [k, f"{v:.2f} kg", f"{(v / flush_total * 100):.1f} %" if flush_total > 0 else "0%"]
                        for k, v in flush_dict.items()
                    ]

                    def export_flush_pdf():
                        cfg = {
                            "title": "Flush Wave Yield Breakdown",
                            "firmName": AppSession.active_firm_name or target_firm_id,
                            "subtitle": f"Total Flush Output: {flush_total:.2f} kg",
                            "containerId": "chart_box_2",
                            "orientation": "portrait",
                            "columns": ["Flush Wave", "Weight Harvested", "Contribution (%)"],
                            "rows": flush_table_rows,
                        }
                        ui.run_javascript(f"window.exportTabularReportPDF({json.dumps(cfg)});")

                    with ui.card().classes("flex-1 min-w-[280px] p-4 border rounded-xl shadow-none bg-white"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            ui.label("Flush Wave Contribution").classes("text-sm font-bold text-gray-800")
                            ui.button("PDF", icon="picture_as_pdf", on_click=export_flush_pdf).classes(
                                "bg-teal-700 text-white rounded-lg text-xs px-2.5 py-1 shadow-none"
                            )

                        flush_data = [
                            {"name": k, "value": v}
                            for k, v in flush_dict.items()
                            if v > 0
                        ]

                        with ui.element('div').props('id="chart_box_2"').classes("w-full h-64"):
                            ui.echart({
                                "tooltip": {"trigger": "item", "formatter": "{b}: {c} kg ({d}%)"},
                                "legend": {"bottom": "0%", "left": "center", "textStyle": {"fontSize": 10}},
                                "series": [{
                                    "type": "pie",
                                    "radius": ["40%", "70%"],
                                    "avoidLabelOverlap": False,
                                    "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                                    "label": {"show": False},
                                    "data": flush_data,
                                }],
                            }).classes("w-full h-full")

                # -------------------------------------------------------------
                # ROW 3: BATCH EFFICIENCY & EXPENSE AUDIT
                # -------------------------------------------------------------
                with ui.row().classes("w-full gap-4"):
                    # 3. Batch Biological Efficiency Card
                    b_data = data.get("batch_be_data", [])
                    batch_table_rows = [
                        [
                            b["code"],
                            f"{b['bags']} Bags",
                            f"{b['yield_kg']:.2f} kg",
                            f"{b['be']:.1f} %",
                            "Target Met" if b['be'] >= 80 else "Sub-optimal",
                        ]
                        for b in b_data
                    ]

                    def export_batches_pdf():
                        cfg = {
                            "title": "Batch Biological Efficiency Audit",
                            "firmName": AppSession.active_firm_name or target_firm_id,
                            "subtitle": f"Year: {filter_state['year']}",
                            "containerId": "chart_box_3",
                            "orientation": "portrait",
                            "columns": ["Batch Code", "Bag Count", "Total Yield", "B.E. (%)", "Audit Status"],
                            "rows": batch_table_rows,
                        }
                        ui.run_javascript(f"window.exportTabularReportPDF({json.dumps(cfg)});")

                    with ui.card().classes("flex-1 min-w-[340px] p-4 border rounded-xl shadow-none bg-white"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            ui.label("Batch Biological Efficiency (%)").classes("text-sm font-bold text-gray-800")
                            ui.button("PDF", icon="picture_as_pdf", on_click=export_batches_pdf).classes(
                                "bg-blue-700 text-white rounded-lg text-xs px-2.5 py-1 shadow-none"
                            )

                        b_codes = [b["code"] for b in b_data]
                        b_bes = [b["be"] for b in b_data]

                        with ui.element('div').props('id="chart_box_3"').classes("w-full h-64"):
                            ui.echart({
                                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                                "xAxis": {"type": "category", "data": b_codes, "axisLabel": {"fontSize": 10}},
                                "yAxis": {"type": "value", "name": "B.E. %"},
                                "series": [{
                                    "data": b_bes,
                                    "type": "bar",
                                    "color": "#0284c7",
                                    "markLine": {
                                        "data": [{"yAxis": 100, "name": "100% Target"}],
                                        "lineStyle": {"color": "#ef4444", "type": "dashed"},
                                    },
                                }],
                                "grid": {"left": "10%", "right": "5%", "bottom": "12%", "top": "15%"},
                            }).classes("w-full h-full")

                    # 4. Operating Expense Categorization Card
                    exp_breakdown = data.get("expense_breakdown", {})
                    total_exp = sum(exp_breakdown.values())
                    expense_table_rows = [
                        [k.replace("_", " "), f"Rs. {v:,.2f}", f"{(v / total_exp * 100):.1f} %" if total_exp > 0 else "0%"]
                        for k, v in exp_breakdown.items()
                    ]

                    def export_expense_pdf():
                        cfg = {
                            "title": "Operational Expense Ledger Report",
                            "firmName": AppSession.active_firm_name or target_firm_id,
                            "subtitle": f"Total Expenditure: Rs. {total_exp:,.2f}",
                            "containerId": "chart_box_4",
                            "orientation": "portrait",
                            "columns": ["Expense Category", "Total Incurred", "Contribution (%)"],
                            "rows": expense_table_rows,
                        }
                        ui.run_javascript(f"window.exportTabularReportPDF({json.dumps(cfg)});")

                    with ui.card().classes("flex-1 min-w-[280px] p-4 border rounded-xl shadow-none bg-white"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            ui.label("Operating Expense Distribution").classes("text-sm font-bold text-gray-800")
                            ui.button("PDF", icon="picture_as_pdf", on_click=export_expense_pdf).classes(
                                "bg-amber-700 text-white rounded-lg text-xs px-2.5 py-1 shadow-none"
                            )

                        exp_data = [
                            {"name": k.replace("_", " "), "value": v}
                            for k, v in exp_breakdown.items()
                            if v > 0
                        ]

                        with ui.element('div').props('id="chart_box_4"').classes("w-full h-64"):
                            ui.echart({
                                "tooltip": {"trigger": "item", "formatter": "₹{c} ({d}%)"},
                                "legend": {"bottom": "0%", "left": "center", "textStyle": {"fontSize": 10}},
                                "series": [{
                                    "type": "pie",
                                    "radius": ["40%", "70%"],
                                    "avoidLabelOverlap": False,
                                    "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                                    "label": {"show": False},
                                    "data": exp_data,
                                }],
                            }).classes("w-full h-full")

        ui.timer(0.05, load_and_render_reports, once=True)