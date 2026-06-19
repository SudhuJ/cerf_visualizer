import fastplotlib as fpl
import numpy as np
import pygfx as gfx
from PIL import Image

from filter import GPUFilterManager
from parse import CerfDataParser
from ui import CerfImGuiPanel


class CerfVisualizer:
    TYPE_NAMES = {0: "Minima", 1: "Saddle-1", 2: "Saddle-2", 3: "Maxima"}

    def __init__(self, initial_filepath):
        self.parser = CerfDataParser()

        self.state = {
            "title": "CERF Diagram",
            "selected_info": "Ready.",
            "import_path": initial_filepath,
            "export_path": "exported_diagram",
            "show_grid": False,
            "grid_size": 10.0,
            "x_intervals": [],
            "y_intervals": [],
            "view_x_min": 0.0,
            "view_x_max": 1.0,
            "view_y_min": 0.0,
            "view_y_max": 1.0,
            "highlight_ids": "",
        }

        self._last_cam_state = None

        self.fig = fpl.Figure(size=(1200, 800), names=[["Cerf Visualizer"]])
        self.fig[0, 0].background_color = ["white"]

        if hasattr(self.fig[0, 0], "toolbar"):
            self.fig[0, 0].toolbar = False

        self.fig[0, 0].axes.world_object.visible = False

        self.x_ruler = gfx.Ruler(tick_side="right", color="black")
        self.y_ruler = gfx.Ruler(tick_side="left", color="black")

        self.x_label = gfx.Text(
            text="Time",
            font_size=18,
            screen_space=True,
            material=gfx.TextMaterial(color="black"),
        )
        self.y_label = gfx.Text(
            text="Function Value",
            font_size=18,
            screen_space=True,
            material=gfx.TextMaterial(color="black"),
        )
        self.y_label.local.rotation = (0.0, 0.0, 0.707106, 0.707106)

        mask_mat = gfx.MeshBasicMaterial(color="white")
        mask_geom = gfx.box_geometry(1, 1, 1)

        self.mask_left = gfx.Mesh(mask_geom, mask_mat)
        self.mask_right = gfx.Mesh(mask_geom, mask_mat)
        self.mask_bottom = gfx.Mesh(mask_geom, mask_mat)
        self.mask_top = gfx.Mesh(mask_geom, mask_mat)

        self.mask_left.local.z = 5
        self.mask_right.local.z = 5
        self.mask_bottom.local.z = 5
        self.mask_top.local.z = 5

        tick_mask_mat = gfx.MeshBasicMaterial(color="white", alpha_mode="solid")
        self.mask_tick_x = gfx.Mesh(mask_geom, tick_mask_mat)
        self.mask_tick_y = gfx.Mesh(mask_geom, tick_mask_mat)
        self.mask_tick_x.local.z = 9
        self.mask_tick_y.local.z = 9

        grid_material = gfx.GridMaterial(
            major_step=(self.state["grid_size"], self.state["grid_size"]),
            minor_step=(self.state["grid_size"] / 10, self.state["grid_size"] / 10),
            major_thickness=1.0,
            major_color="#E5E5E5",
            infinite=True,
        )
        self.grid = gfx.Grid(None, grid_material, orientation="xy")
        self.grid.local.z = -5
        self.grid.visible = self.state["show_grid"]

        self.fig[0, 0].scene.add(
            self.grid,
            self.mask_left,
            self.mask_right,
            self.mask_bottom,
            self.mask_top,
            self.mask_tick_x,
            self.mask_tick_y,
            self.x_ruler,
            self.y_ruler,
            self.x_label,
            self.y_label,
        )

        self.cerf_graphics = {}
        self.highlight_graphics = []
        self._load_and_draw(initial_filepath)
        self._setup_gui()
        self._setup_keybinds()
        self.fig.add_animations(self._update_screen_locked_ui)

    def _setup_keybinds(self):
        def on_key_down(event):
            # Ignore if typing in a textbox or modifying with Ctrl/Alt
            if getattr(event, "modifiers", None) or event.key is None:
                return

            key = event.key.lower()

            # Camera Reset (R)
            if key == "r":
                self.reset_viewport()
                self.state["selected_info"] = "Viewport reset (Key: R)"

            # Critical Point Filters (0, 1, 2, 3)
            elif key in ["0", "1", "2", "3"]:
                cp_type = int(key)
                state_key = f"show_type_{cp_type}"

                # Fetch current state (defaulting to True if UI hasn't set it yet)
                current_state = self.state.get(state_key, True)
                new_state = not current_state

                # 1. Update the state dictionary (Syncs the ImGui Checkbox)
                self.state[state_key] = new_state

                # 2. Fire the visual filter update
                self.apply_type_filter(cp_type, new_state)

                status = "Shown" if new_state else "Hidden"
                name = self.TYPE_NAMES.get(cp_type, "Unknown")
                self.state["selected_info"] = f"{name} {status} (Key: {key})"

        # Attach the listener to the core renderer
        self.fig.renderer.add_event_handler(on_key_down, "key_down")

    def _update_screen_locked_ui(self, *args):
        if not getattr(self, "x_label", None):
            return

        cam = getattr(self.fig[0, 0].camera, "world_object", self.fig[0, 0].camera)
        if not hasattr(cam, "width"):
            return

        zoom = cam.zoom
        cam_x, cam_y, _ = cam.local.position

        current_cam_state = (cam_x, cam_y, zoom, cam.width, cam.height)
        if self._last_cam_state == current_cam_state:
            return

        self._last_cam_state = current_cam_state

        w = cam.width / zoom
        h = cam.height / zoom
        left, right = cam_x - (w / 2), cam_x + (w / 2)
        bottom, top = cam_y - (h / 2), cam_y + (h / 2)
        x_margin, y_margin = w * 0.04, h * 0.04

        axis_x_pos, axis_right_pos = left + x_margin, right - x_margin
        axis_y_pos, axis_top_pos = bottom + y_margin, top - y_margin

        self.x_ruler.start_pos = (axis_x_pos, axis_y_pos, 10)
        self.x_ruler.end_pos = (axis_right_pos, axis_y_pos, 10)
        self.x_ruler.start_value = axis_x_pos

        self.y_ruler.start_pos = (axis_x_pos, axis_y_pos, 10)
        self.y_ruler.end_pos = (axis_x_pos, axis_top_pos, 10)
        self.y_ruler.start_value = axis_y_pos

        self.x_label.local.position = (cam_x, axis_y_pos - (y_margin * 0.75), 10)
        self.y_label.local.position = (axis_x_pos - (x_margin * 0.75), cam_y, 10)

        try:
            canvas_size = self.fig.canvas.get_logical_size()
        except Exception:
            canvas_size = (1200, 800)

        self.x_ruler.update(cam, canvas_size)
        self.y_ruler.update(cam, canvas_size)

        WALL_SIZE = 100000.0
        mask_w_center = axis_right_pos - axis_x_pos

        self.mask_left.local.scale = (WALL_SIZE, WALL_SIZE, 1)
        self.mask_left.local.x = axis_x_pos - (WALL_SIZE / 2)
        self.mask_left.local.y = cam_y

        self.mask_right.local.scale = (WALL_SIZE, WALL_SIZE, 1)
        self.mask_right.local.x = axis_right_pos + (WALL_SIZE / 2)
        self.mask_right.local.y = cam_y

        self.mask_bottom.local.scale = (mask_w_center, WALL_SIZE, 1)
        self.mask_bottom.local.x = cam_x
        self.mask_bottom.local.y = axis_y_pos - (WALL_SIZE / 2)

        self.mask_top.local.scale = (mask_w_center, WALL_SIZE, 1)
        self.mask_top.local.x = cam_x
        self.mask_top.local.y = axis_top_pos + (WALL_SIZE / 2)

        x_tick_h = y_margin
        self.mask_tick_x.local.scale = (mask_w_center, x_tick_h, 1)
        self.mask_tick_x.local.x = cam_x
        self.mask_tick_x.local.y = axis_y_pos - (x_tick_h / 2)

        y_tick_w = x_margin
        self.mask_tick_y.local.scale = (y_tick_w, axis_top_pos - axis_y_pos, 1)
        self.mask_tick_y.local.x = axis_x_pos - (y_tick_w / 2)
        self.mask_tick_y.local.y = cam_y

    def _load_and_draw(self, filepath):
        try:
            self.positions_by_type, self.metadata_by_type = (
                self.parser.load_and_process(filepath)
            )

            # Cleanup old geometry
            if hasattr(self, "cerf_graphics"):
                for g in self.cerf_graphics.values():
                    self.fig[0, 0].remove(g)

            # Cleanup highlights on reload
            if hasattr(self, "highlight_graphics") and self.highlight_graphics:
                for g in self.highlight_graphics:
                    self.fig[0, 0].remove(g)
                self.highlight_graphics = []

            if hasattr(self.fig[0, 0].camera, "maintain_aspect"):
                self.fig[0, 0].camera.maintain_aspect = False

            self.cerf_graphics = {}

            # Draw order ensures Grey is drawn first in the background
            draw_order = sorted(
                self.positions_by_type.keys(),
                key=lambda k: len(self.positions_by_type[k]),
                reverse=True,
            )

            for cp_type in draw_order:
                pos_data = self.positions_by_type[cp_type]
                uniform_color = tuple(self.parser.color_map[cp_type])

                line_graphic = self.fig[0, 0].add_line(
                    data=pos_data,
                    colors=uniform_color,
                    uniform_color=True,
                    thickness=1.0,
                    name=f"cerf_diagram_{cp_type}",
                )
                self.cerf_graphics[cp_type] = line_graphic

            # Initialize filter manager with dictionaries
            self.filter_manager = GPUFilterManager(
                self.cerf_graphics, self.positions_by_type
            )

            # Calculate global bounding box
            all_x = np.concatenate(
                [pos[:, 0] for pos in self.positions_by_type.values()]
            )
            all_y = np.concatenate(
                [pos[:, 1] for pos in self.positions_by_type.values()]
            )

            x_min, x_max = float(np.nanmin(all_x)), float(np.nanmax(all_x))
            y_min, y_max = float(np.nanmin(all_y)), float(np.nanmax(all_y))

            self.state["data_x_range"] = (x_min, x_max)
            self.state["data_y_range"] = (y_min, y_max)
            self.state["x_intervals"] = [[x_min, x_max]]
            self.state["y_intervals"] = [[y_min, y_max]]

            max_range = max(x_max - x_min, y_max - y_min)
            if max_range > 0:
                new_size = max(round(max_range / 10.0, 1), 0.1)
                self.state["grid_size"] = new_size
                if hasattr(self, "grid"):
                    self.grid.material.major_step = (new_size, new_size)
                    self.grid.material.minor_step = (new_size / 10, new_size / 10)

            self.state["selected_info"] = f"Successfully loaded {filepath}"

            self.reset_viewport()

        except Exception as e:
            self.state["selected_info"] = f"Error loading file: {str(e)}"

    def _setup_gui(self):
        callbacks = {
            "import_data": self.import_file,
            "export_data": self.export_file,
            "export_raw": self.export_raw_data,
            "toggle_grid": self.toggle_grid,
            "update_grid": self.update_grid_size,
            "apply_type_filter": self.apply_type_filter,
            "apply_range_filters": self.apply_range_filters,
            "apply_viewport": self.apply_viewport,
            "reset_viewport": self.reset_viewport,
            "apply_highlights": self.apply_highlights,
        }

        gui = CerfImGuiPanel(
            figure=self.fig,
            state_manager=self.state,
            callbacks=callbacks,
            size=350,
            location="right",
            title="CERF Pipeline Tools",
        )
        self.fig.add_gui(gui)

    def apply_highlights(self, ids_string: str):
        # 1. Parse IDs safely
        try:
            raw_ids = [x.strip() for x in ids_string.split(",") if x.strip()]
            target_ids = set(int(x) for x in raw_ids)
        except ValueError:
            self.state["selected_info"] = (
                "Invalid ID format. Use integers separated by commas."
            )
            return

        # 2. Clear existing highlights from the canvas
        if hasattr(self, "highlight_graphics") and self.highlight_graphics:
            for g in self.highlight_graphics:
                self.fig[0, 0].remove(g)
        self.highlight_graphics = []

        if not target_ids:
            self.state["selected_info"] = "Highlights cleared."
            return

        highlight_positions = []

        # 3. Search and extract geometry from the parsed data
        for cp_type, meta in self.metadata_by_type.items():
            # Column index 4 in metadata maps to the 6th column (Vertex ID) in the raw file
            v_ids = meta[:, 4]
            mask = np.isin(v_ids, list(target_ids))

            if not np.any(mask):
                continue

            # The positions buffer is flattened to (N*3, 3) for fastplotlib.
            pos_reshaped = self.positions_by_type[cp_type].reshape(-1, 3, 3)
            matched_pos = pos_reshaped[mask].reshape(-1, 3)

            # Bump the Z-coordinate slightly so it renders strictly on top of base lines
            matched_pos[:, 2] = 0.5
            highlight_positions.append(matched_pos)

        # 4. Render Highlights
        if not highlight_positions:
            self.state["selected_info"] = f"No segments found for IDs: {ids_string}"
            return

        all_highlight_pos = np.concatenate(highlight_positions)

        # Draw dedicated overlay graphic
        hg = self.fig[0, 0].add_line(
            data=all_highlight_pos,
            colors=(1.0, 0.9, 0.0, 0.7),
            uniform_color=True,
            thickness=8.0,
            name="vertex_highlights",
        )

        self.highlight_graphics.append(hg)
        self.state["selected_info"] = f"Highlighted {len(target_ids)} vertex IDs."

    def apply_viewport(self):
        vx_min, vx_max = self.state["view_x_min"], self.state["view_x_max"]
        vy_min, vy_max = self.state["view_y_min"], self.state["view_y_max"]

        if vx_min >= vx_max or vy_min >= vy_max:
            self.state["selected_info"] = "Invalid Viewport Bounds."
            return

        cam = self.fig[0, 0].camera
        cam.local.x = (vx_max + vx_min) / 2.0
        cam.local.y = (vy_max + vy_min) / 2.0

        cam.width = vx_max - vx_min
        cam.height = vy_max - vy_min
        cam.zoom = 1.0

    def reset_viewport(self):
        if "data_x_range" not in self.state:
            return

        dx_min, dx_max = self.state["data_x_range"]
        dy_min, dy_max = self.state["data_y_range"]

        width = dx_max - dx_min
        height = dy_max - dy_min

        if width == 0:
            width = 1.0
        if height == 0:
            height = 1.0

        margin_x = width * 0.05
        margin_y = height * 0.05

        self.state["view_x_min"] = dx_min - margin_x
        self.state["view_x_max"] = dx_max + margin_x
        self.state["view_y_min"] = dy_min - margin_y
        self.state["view_y_max"] = dy_max + margin_y

        self.apply_viewport()

    def apply_type_filter(self, cp_type: int, show: bool):
        # Instantly drops/adds the geometry from the hardware render pipeline
        if hasattr(self, "cerf_graphics") and cp_type in self.cerf_graphics:
            self.cerf_graphics[cp_type].visible = show

    def apply_range_filters(self):
        if not hasattr(self, "filter_manager"):
            return
        # Pushes calculation entirely to the GPU Filter Manager
        self.filter_manager.set_spatial_intervals(
            self.state["x_intervals"], self.state["y_intervals"]
        )

    def update_grid_size(self, size: float):
        self.state["grid_size"] = size
        if hasattr(self, "grid"):
            self.grid.material.major_step = (size, size)

    def toggle_grid(self, show: bool):
        self.state["show_grid"] = show
        if hasattr(self, "grid"):
            self.grid.visible = show

    def import_file(self, filepath: str):
        self._load_and_draw(filepath)

    def export_file(self, filepath: str):
        try:
            from rendercanvas.offscreen import RenderCanvas

            if not filepath.lower().endswith(".png"):
                filepath += ".png"
            self.state["export_path"] = filepath

            try:
                canvas_size = self.fig.canvas.get_logical_size()
                aspect_ratio = canvas_size[1] / canvas_size[0]
            except Exception:
                aspect_ratio = 1080 / 1920

            export_width = 1920
            export_height = int(export_width * aspect_ratio)

            offscreen_canvas = RenderCanvas(size=(export_width, export_height))
            offscreen_renderer = gfx.WgpuRenderer(offscreen_canvas)

            offscreen_renderer.render(
                self.fig[0, 0].scene,
                self.fig[0, 0].camera,
                clear_color=(1.0, 1.0, 1.0, 1.0),
            )
            img_array = np.asarray(offscreen_canvas.draw())

            if img_array is None or img_array.size == 0:
                raise ValueError("Offscreen renderer returned empty data.")

            Image.fromarray(img_array).save(filepath)
            self.state["selected_info"] = (
                f"Successfully exported clean plot to {filepath}"
            )

        except Exception as e:
            self.state["selected_info"] = f"Error exporting file: {str(e)}"

    def export_raw_data(self, filepath: str):
        try:
            if not filepath.lower().endswith(".txt"):
                filepath += ".txt"
            self.parser.save_data(filepath)
            self.state["selected_info"] = f"Successfully saved raw data to {filepath}"
        except Exception as e:
            self.state["selected_info"] = f"Error saving text file: {str(e)}"

    def show(self):
        self.fig.show()
        self.reset_viewport()
        fpl.loop.run()
