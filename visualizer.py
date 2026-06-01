import fastplotlib as fpl
import numpy as np
import pygfx as gfx
from PIL import Image

from filter import GPUFilterManager
from parse import CerfDataParser
from ui import CerfImGuiPanel


class CerfVisualizer:
    TYPE_NAMES = {0: "Minima", 1: "Saddle", 2: "Maxima", 3: "Unknown"}

    def __init__(self, initial_filepath):
        self.parser = CerfDataParser()

        self.state = {
            "title": "CERF Diagram",
            "selected_info": "No point selected.",
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
        }

        # State tracker to prevent CPU thrashing during UI updates
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
            self.x_ruler,
            self.y_ruler,
            self.x_label,
            self.y_label,
        )

        self._load_and_draw(initial_filepath)
        self._setup_gui()
        self.fig.add_animations(self._update_screen_locked_ui)

    def _update_screen_locked_ui(self, *args):
        if not getattr(self, "x_label", None):
            return

        cam = getattr(self.fig[0, 0].camera, "world_object", self.fig[0, 0].camera)
        if not hasattr(cam, "width"):
            return

        zoom = cam.zoom
        cam_x, cam_y, _ = cam.local.position

        # Check if the camera has actually moved before rebuilding UI geometry
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

    def _load_and_draw(self, filepath):
        try:
            self.positions, self.colors, self.metadata = self.parser.load_and_process(
                filepath
            )

            if hasattr(self, "cerf_graphic") and self.cerf_graphic is not None:
                self.fig[0, 0].remove(self.cerf_graphic)

            if hasattr(self.fig[0, 0].camera, "maintain_aspect"):
                self.fig[0, 0].camera.maintain_aspect = False

            self.cerf_graphic = self.fig[0, 0].add_line(
                data=self.positions,
                colors=self.colors,
                thickness=1.5,
                name="cerf_diagram",
            )

            # Pass self.positions to utilize NaN discarding optimization
            self.filter_manager = GPUFilterManager(
                self.cerf_graphic, self.positions, self.metadata
            )

            x_min = float(np.nanmin(self.positions[:, 0]))
            y_min = float(np.nanmin(self.positions[:, 1]))
            x_max = float(np.nanmax(self.positions[:, 0]))
            y_max = float(np.nanmax(self.positions[:, 1]))

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

            self._bind_events()
            self.state["selected_info"] = f"Successfully loaded {filepath}"

            # Snap camera to dataset exactly on load
            self.reset_viewport()

        except Exception as e:
            self.state["selected_info"] = f"Error loading file: {str(e)}"

    def _bind_events(self):
        @self.cerf_graphic.add_event_handler("click")
        def on_vertex_click(event):
            picked_idx = event.index
            if picked_idx is None:
                return

            original_idx = picked_idx // 3
            if original_idx >= len(self.metadata):
                return

            meta = self.metadata[original_idx]
            x, y, z = meta[0], meta[1], meta[2]
            cp_type = int(meta[3])
            vertex_id = int(meta[4])

            self.state["selected_info"] = (
                f"Vertex ID: {vertex_id}\n"
                f"Type: {self.TYPE_NAMES.get(cp_type, 'N/A')} \n"
                f"x={x:.4f}, y={y:.4f}, z={z:.4f}"
            )

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

    def apply_viewport(self):
        """Forces the camera bounds to match the manual text inputs exactly."""
        vx_min, vx_max = self.state["view_x_min"], self.state["view_x_max"]
        vy_min, vy_max = self.state["view_y_min"], self.state["view_y_max"]

        if vx_min >= vx_max or vy_min >= vy_max:
            self.state["selected_info"] = "Invalid Viewport Bounds."
            return

        cam = self.fig[0, 0].camera
        cam.local.x = (vx_max + vx_min) / 2.0
        cam.local.y = (vy_max + vy_min) / 2.0

        # Override frustum size and reset zoom so exact dimensions match screen edges
        cam.width = vx_max - vx_min
        cam.height = vy_max - vy_min
        cam.zoom = 1.0

    def reset_viewport(self):
        """Resets the view to automatically frame the entire dataset with a 5% margin."""
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
        if not hasattr(self, "filter_manager"):
            return

        filter_name = f"hide_cp_type_{cp_type}"
        if show:
            self.filter_manager.remove_filter(filter_name)
        else:
            mask = self.metadata[:, 3] != cp_type
            self.filter_manager.set_filter(filter_name, mask)

    def apply_range_filters(self):
        """Calculates masks for multiple spatial intervals using fast 1D AABB intersections."""
        if not hasattr(self, "filter_manager"):
            return

        x_starts = self.positions[0::3, 0]
        x_ends = self.positions[1::3, 0]
        y_starts = self.positions[0::3, 1]
        y_ends = self.positions[1::3, 1]

        seg_x_min, seg_x_max = (
            np.minimum(x_starts, x_ends),
            np.maximum(x_starts, x_ends),
        )
        seg_y_min, seg_y_max = (
            np.minimum(y_starts, y_ends),
            np.maximum(y_starts, y_ends),
        )

        if not self.state["x_intervals"]:
            mask_x = np.zeros(len(x_starts), dtype=bool)
        else:
            mask_x = np.zeros(len(x_starts), dtype=bool)
            for x_min, x_max in self.state["x_intervals"]:
                mask_x |= (seg_x_min <= x_max) & (seg_x_max >= x_min)

        if not self.state["y_intervals"]:
            mask_y = np.zeros(len(y_starts), dtype=bool)
        else:
            mask_y = np.zeros(len(y_starts), dtype=bool)
            for y_min, y_max in self.state["y_intervals"]:
                mask_y |= (seg_y_min <= y_max) & (seg_y_max >= y_min)

        self.filter_manager.set_filter("x_range", mask_x)
        self.filter_manager.set_filter("y_range", mask_y)

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
        fpl.loop.run()
