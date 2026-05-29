import fastplotlib as fpl
import numpy as np
import pygfx as gfx
from PIL import Image

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
        }

        self.fig = fpl.Figure(size=(1200, 800))
        self.fig[0, 0].background_color = ["white"]
        self.fig[0, 0].name = " "

        if hasattr(self.fig[0, 0], "toolbar"):
            self.fig[0, 0].toolbar = False

        # 1. DISABLE FASTPLOTLIB'S BUILT-IN AXES
        self.fig[0, 0].axes.world_object.visible = False

        # 2. CREATE OUR OWN STANDALONE PYGFX RULERS
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

        # 3. CREATE PHYSICAL UI MASKS (Massive walls to permanently block non-plot areas)
        mask_mat = gfx.MeshBasicMaterial(color="white")
        mask_geom = gfx.box_geometry(1, 1, 1)

        self.mask_left = gfx.Mesh(mask_geom, mask_mat)
        self.mask_right = gfx.Mesh(mask_geom, mask_mat)
        self.mask_bottom = gfx.Mesh(mask_geom, mask_mat)
        self.mask_top = gfx.Mesh(mask_geom, mask_mat)

        # Place the masks in front of the data (Z=0), but behind the UI (Z=10)
        self.mask_left.local.z = 5
        self.mask_right.local.z = 5
        self.mask_bottom.local.z = 5
        self.mask_top.local.z = 5

        # 4. CREATE FAINT INFINITE GRID
        # 10,000 units wide with 1,000 divisions = 10 units per square.
        # #E5E5E5 provides a very faint, non-intrusive light gray line.
        self.grid_helper = gfx.GridHelper(
            size=10000, divisions=1000, color1="#E5E5E5", color2="#E5E5E5"
        )

        # Rotate 90 degrees around X-axis to align with the data's XY plane (Quat: x,y,z,w)
        self.grid_helper.local.rotation = (0.707106, 0.0, 0.0, 0.707106)
        self.grid_helper.local.z = -5  # Keep it far behind the plotted data (Z=0)
        self.grid_helper.visible = self.state["show_grid"]

        # Add everything to the scene
        self.fig[0, 0].scene.add(
            self.grid_helper,
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

        # Attach the dynamic screen-locking function to the render loop
        self.fig.add_animations(self._update_screen_locked_ui)

    def _update_screen_locked_ui(self, *args):
        """Runs every frame. Keeps the standalone rulers dynamic and glued to the screen boundaries,
        and manages the massive UI masks to frame the data area."""

        if not getattr(self, "x_label", None):
            return

        cam = getattr(self.fig[0, 0].camera, "world_object", self.fig[0, 0].camera)
        if not hasattr(cam, "width"):
            return

        zoom = cam.zoom
        cam_x, cam_y, _ = cam.local.position

        if hasattr(self, "grid_helper"):
            self.grid_helper.local.x = round(cam_x / 10) * 10
            self.grid_helper.local.y = round(cam_y / 10) * 10

        # Calculate the visible world dimensions based on camera zoom
        w = cam.width / zoom
        h = cam.height / zoom

        # Absolute world coordinates of the camera edges
        left = cam_x - (w / 2)
        right = cam_x + (w / 2)
        bottom = cam_y - (h / 2)
        top = cam_y + (h / 2)

        # Tight 4% margin for maximum plot visibility
        x_margin = w * 0.04
        y_margin = h * 0.04

        axis_x_pos = left + x_margin
        axis_y_pos = bottom + y_margin
        axis_right_pos = right - x_margin
        axis_top_pos = top - y_margin

        # --- 1. UPDATE RULERS & LABELS ---
        # THE FIX: Restore the Z=10 coordinate so they sit visually on top of the Z=5 masks!
        self.x_ruler.start_pos = (axis_x_pos, axis_y_pos, 10)
        self.x_ruler.end_pos = (axis_right_pos, axis_y_pos, 10)
        self.x_ruler.start_value = axis_x_pos

        self.y_ruler.start_pos = (axis_x_pos, axis_y_pos, 10)
        self.y_ruler.end_pos = (axis_x_pos, axis_top_pos, 10)
        self.y_ruler.start_value = axis_y_pos

        # Snug the text labels up relative to the tight margin
        self.x_label.local.position = (cam_x, axis_y_pos - (y_margin * 0.75), 10)
        self.y_label.local.position = (axis_x_pos - (x_margin * 0.75), cam_y, 10)

        # Trigger internal Ruler updates to recalculate ticks based on the new dynamic position
        try:
            canvas_size = self.fig.canvas.get_logical_size()
        except Exception:
            canvas_size = (1200, 800)
        self.x_ruler.update(cam, canvas_size)
        self.y_ruler.update(cam, canvas_size)

        # --- 2. UPDATE PHYSICAL MASKS (The 4-sided Infinite Picture Frame) ---
        # By making the masks 100,000 units large, we ensure they infinitely block
        # the margins, completely solving the offscreen-export leakage bug.
        WALL_SIZE = 100000.0
        mask_w_center = axis_right_pos - axis_x_pos

        # Left Mask
        self.mask_left.local.scale = (WALL_SIZE, WALL_SIZE, 1)
        self.mask_left.local.x = axis_x_pos - (WALL_SIZE / 2)
        self.mask_left.local.y = cam_y

        # Right Mask
        self.mask_right.local.scale = (WALL_SIZE, WALL_SIZE, 1)
        self.mask_right.local.x = axis_right_pos + (WALL_SIZE / 2)
        self.mask_right.local.y = cam_y

        # Bottom Mask (Fits between left/right masks)
        self.mask_bottom.local.scale = (mask_w_center, WALL_SIZE, 1)
        self.mask_bottom.local.x = cam_x
        self.mask_bottom.local.y = axis_y_pos - (WALL_SIZE / 2)

        # Top Mask (Fits between left/right masks)
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

            x_min = np.nanmin(self.positions[:, 0])
            y_min = np.nanmin(self.positions[:, 1])
            x_max = np.nanmax(self.positions[:, 0])
            y_max = np.nanmax(self.positions[:, 1])

            # Frame the camera nicely over the data center
            self.fig[0, 0].camera.local.x = (x_max + x_min) / 2
            self.fig[0, 0].camera.local.y = (y_max + y_min) / 2

            self._bind_events()
            self.state["selected_info"] = f"Successfully loaded {filepath}"

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
        }

        gui = CerfImGuiPanel(
            figure=self.fig,
            state_manager=self.state,
            callbacks=callbacks,
            size=300,
            location="right",
            title="CERF Pipeline Tools",
        )
        self.fig.add_gui(gui)

    def toggle_grid(self, show: bool):
        self.state["show_grid"] = show
        if hasattr(self, "grid_helper"):
            self.grid_helper.visible = show

    def import_file(self, filepath: str):
        self._load_and_draw(filepath)

    def export_file(self, filepath: str):
        try:
            from rendercanvas.offscreen import RenderCanvas

            if not filepath.lower().endswith(".png"):
                filepath += ".png"
                self.state["export_path"] = filepath

            # Maintain the aspect ratio of the live window for a 1:1 accurate export
            try:
                canvas_size = self.fig.canvas.get_logical_size()
                aspect_ratio = canvas_size[1] / canvas_size[0]
            except Exception:
                aspect_ratio = 1080 / 1920

            export_width = 1920
            export_height = int(export_width * aspect_ratio)

            offscreen_canvas = RenderCanvas(size=(export_width, export_height))
            offscreen_renderer = gfx.WgpuRenderer(offscreen_canvas)

            scene = self.fig[0, 0].scene
            camera = self.fig[0, 0].camera

            offscreen_renderer.render(scene, camera, clear_color=(1.0, 1.0, 1.0, 1.0))

            img_array = np.asarray(offscreen_canvas.draw())

            if img_array is None or img_array.size == 0:
                raise ValueError("Offscreen renderer returned empty data.")

            img = Image.fromarray(img_array)
            img.save(filepath)
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
