from fastplotlib.ui import EdgeWindow
from imgui_bundle import imgui


class CerfImGuiPanel(EdgeWindow):
    """Custom ImGui Sidebar Panel."""

    def __init__(self, figure, state_manager, callbacks, size, location, title):
        super().__init__(figure=figure, size=size, location=location, title=title)
        self.state = state_manager
        self.callbacks = callbacks

    def update(self):
        """Called every frame by the WebGPU render loop."""

        btn_width = imgui.get_content_region_avail().x

        # --- 1. Import ---
        imgui.text("Data Import")
        imgui.set_next_item_width(-1)
        _, self.state["import_path"] = imgui.input_text(
            "##import", self.state["import_path"]
        )

        if imgui.button("Load File", size=(btn_width, 0)):
            self.callbacks["import_data"](self.state["import_path"])

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 2. Export ---
        imgui.text("Data Export")
        imgui.set_next_item_width(-1)
        _, self.state["export_path"] = imgui.input_text(
            "##export", self.state["export_path"]
        )

        if imgui.button("Save PNG", size=(btn_width, 0)):
            self.callbacks["export_data"](self.state["export_path"])

        if imgui.button("Save TXT", size=(btn_width, 0)):
            self.callbacks["export_raw"](self.state["export_path"])

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 3. System Status ---
        imgui.text("System Status:")
        imgui.text_colored((0.2, 0.6, 1.0, 1.0), self.state["selected_info"])

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 4. View Options ---
        imgui.text("View Options")

        changed_toggle, self.state["show_grid"] = imgui.checkbox(
            "Show Faint Grid", self.state.get("show_grid", False)
        )

        if changed_toggle and "toggle_grid" in self.callbacks:
            self.callbacks["toggle_grid"](self.state["show_grid"])

        imgui.set_next_item_width(-1)
        changed_size, new_size = imgui.drag_float(
            "##gridsize",
            self.state.get("grid_size", 10.0),
            v_speed=0.5,
            v_min=0.1,
            v_max=10000.0,
            format="Grid Size: %.1f",
        )

        if changed_size and "update_grid" in self.callbacks:
            self.callbacks["update_grid"](new_size)

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 5. Vertex Highlighting ---
        imgui.text("Vertex Highlighting")
        imgui.text_colored((0.7, 0.7, 0.7, 1.0), "Comma-separated IDs")

        imgui.set_next_item_width(-1)
        changed_hl, self.state["highlight_ids"] = imgui.input_text(
            "##highlight_ids", self.state.get("highlight_ids", "")
        )

        if imgui.button("Apply Highlights", size=(btn_width, 0)):
            if "apply_highlights" in self.callbacks:
                self.callbacks["apply_highlights"](self.state["highlight_ids"])

        if imgui.button("Clear Highlights", size=(btn_width, 0)):
            self.state["highlight_ids"] = ""
            if "apply_highlights" in self.callbacks:
                self.callbacks["apply_highlights"]("")

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 6. Categorical Filters ---
        imgui.text("Categorical Filters")

        filter_options = [
            (0, "Minima (Blue)"),
            (1, "Saddle (Green)"),
            (2, "Maxima (Red)"),
            (3, "Non-Critical (Grey)"),
        ]

        for cp_type, label in filter_options:
            state_key = f"show_type_{cp_type}"
            if state_key not in self.state:
                self.state[state_key] = True

            changed, self.state[state_key] = imgui.checkbox(
                f"Show {label}", self.state[state_key]
            )

            if changed and "apply_type_filter" in self.callbacks:
                self.callbacks["apply_type_filter"](cp_type, self.state[state_key])

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 7. Multi-Interval Spatial Filters ---
        imgui.text("Spatial Interval Filters")

        if "data_x_range" in self.state:
            x_min_bound, x_max_bound = self.state["data_x_range"]
            y_min_bound, y_max_bound = self.state["data_y_range"]

            x_speed = max((x_max_bound - x_min_bound) * 0.005, 0.01)
            y_speed = max((y_max_bound - y_min_bound) * 0.005, 0.01)

            any_range_changed = False

            # --- X INTERVALS ---
            imgui.text_colored((0.7, 0.7, 0.7, 1.0), "X-Axis Intervals")

            intervals_to_remove_x = []
            for i, interval in enumerate(self.state["x_intervals"]):
                imgui.push_id(f"x_int_{i}")

                imgui.set_next_item_width(btn_width * 0.35)
                c1, interval[0] = imgui.drag_float(
                    "##xmin",
                    interval[0],
                    v_speed=x_speed,
                    v_min=x_min_bound,
                    v_max=interval[1],
                )

                imgui.same_line()
                imgui.set_next_item_width(btn_width * 0.35)
                c2, interval[1] = imgui.drag_float(
                    "##xmax",
                    interval[1],
                    v_speed=x_speed,
                    v_min=interval[0],
                    v_max=x_max_bound,
                )

                imgui.same_line()
                if imgui.button("X"):
                    intervals_to_remove_x.append(i)

                imgui.pop_id()
                if c1 or c2:
                    any_range_changed = True

            for i in reversed(intervals_to_remove_x):
                self.state["x_intervals"].pop(i)
                any_range_changed = True

            if imgui.button("+ Add X Interval", size=(btn_width, 0)):
                self.state["x_intervals"].append([x_min_bound, x_max_bound])
                any_range_changed = True

            imgui.spacing()

            # --- Y INTERVALS ---
            imgui.text_colored((0.7, 0.7, 0.7, 1.0), "Y-Axis Intervals")

            intervals_to_remove_y = []
            for i, interval in enumerate(self.state["y_intervals"]):
                imgui.push_id(f"y_int_{i}")

                imgui.set_next_item_width(btn_width * 0.35)
                c1, interval[0] = imgui.drag_float(
                    "##ymin",
                    interval[0],
                    v_speed=y_speed,
                    v_min=y_min_bound,
                    v_max=interval[1],
                )

                imgui.same_line()
                imgui.set_next_item_width(btn_width * 0.35)
                c2, interval[1] = imgui.drag_float(
                    "##ymax",
                    interval[1],
                    v_speed=y_speed,
                    v_min=interval[0],
                    v_max=y_max_bound,
                )

                imgui.same_line()
                if imgui.button("X"):
                    intervals_to_remove_y.append(i)

                imgui.pop_id()
                if c1 or c2:
                    any_range_changed = True

            for i in reversed(intervals_to_remove_y):
                self.state["y_intervals"].pop(i)
                any_range_changed = True

            if imgui.button("+ Add Y Interval", size=(btn_width, 0)):
                self.state["y_intervals"].append([y_min_bound, y_max_bound])
                any_range_changed = True

            imgui.spacing()

            if any_range_changed and "apply_range_filters" in self.callbacks:
                self.callbacks["apply_range_filters"]()

            if imgui.button("Reset Filters to Default", size=(btn_width, 0)):
                self.state["x_intervals"] = [[x_min_bound, x_max_bound]]
                self.state["y_intervals"] = [[y_min_bound, y_max_bound]]
                if "apply_range_filters" in self.callbacks:
                    self.callbacks["apply_range_filters"]()

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- 8. Viewport Camera Controls ---
        imgui.text("Viewport Axes Limits")

        imgui.text_colored((0.7, 0.7, 0.7, 1.0), "Time (X) Range")
        imgui.set_next_item_width(btn_width * 0.45)
        changed_vx1, self.state["view_x_min"] = imgui.input_float(
            "##vxm", self.state.get("view_x_min", 0.0)
        )
        imgui.same_line()
        imgui.set_next_item_width(btn_width * 0.45)
        changed_vx2, self.state["view_x_max"] = imgui.input_float(
            "##vxmx", self.state.get("view_x_max", 1.0)
        )

        imgui.text_colored((0.7, 0.7, 0.7, 1.0), "Function Value (Y) Range")
        imgui.set_next_item_width(btn_width * 0.45)
        changed_vy1, self.state["view_y_min"] = imgui.input_float(
            "##vym", self.state.get("view_y_min", 0.0)
        )
        imgui.same_line()
        imgui.set_next_item_width(btn_width * 0.45)
        changed_vy2, self.state["view_y_max"] = imgui.input_float(
            "##vymx", self.state.get("view_y_max", 1.0)
        )

        imgui.spacing()
        if imgui.button("Apply Camera Viewport", size=(btn_width, 0)):
            if "apply_viewport" in self.callbacks:
                self.callbacks["apply_viewport"]()

        if imgui.button("Reset View to Default", size=(btn_width, 0)):
            if "reset_viewport" in self.callbacks:
                self.callbacks["reset_viewport"]()

        imgui.spacing()
