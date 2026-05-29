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

        # ==========================================
        # VERTICAL SIDEBAR LAYOUT
        # ==========================================

        # Calculate the maximum available width for buttons
        btn_width = imgui.get_content_region_avail().x

        # --- 1. Import ---
        imgui.text("Data Import")
        imgui.set_next_item_width(-1)  # -1 forces the input to fill the column width
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

        # --- 3. Selection Status ---
        imgui.text("Selection Status:")

        # Draw the selected info text
        imgui.text_colored((0.2, 0.6, 1.0, 1.0), self.state["selected_info"])

        imgui.spacing()
        if imgui.button("Clear Selection", size=(btn_width, 0)):
            self.state["selected_info"] = "No point selected."
