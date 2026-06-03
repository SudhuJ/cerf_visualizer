import numpy as np


# Replace your GPUFilterManager class in filter.py with this optimized version:
class GPUFilterManager:
    def __init__(self, graphics_dict, base_positions_dict):
        self.graphics = graphics_dict
        self.base_positions = {k: v.copy() for k, v in base_positions_dict.items()}

        # PRE-COMPUTE: Calculate AABB bounds once on initialization
        self.bounds = {}
        for cp_type, base_pos in self.base_positions.items():
            x_starts, x_ends = base_pos[0::3, 0], base_pos[1::3, 0]
            y_starts, y_ends = base_pos[0::3, 1], base_pos[1::3, 1]
            self.bounds[cp_type] = {
                "x_min": np.minimum(x_starts, x_ends),
                "x_max": np.maximum(x_starts, x_ends),
                "y_min": np.minimum(y_starts, y_ends),
                "y_max": np.maximum(y_starts, y_ends),
            }

    def set_spatial_intervals(self, x_intervals, y_intervals):
        for cp_type, base_pos in self.base_positions.items():
            if cp_type not in self.graphics:
                continue

            bounds = self.bounds[cp_type]
            n_segments = len(bounds["x_min"])

            # X-Axis Check
            mask_x = (
                np.ones(n_segments, dtype=bool)
                if not x_intervals
                else np.zeros(n_segments, dtype=bool)
            )
            for x_min, x_max in x_intervals:
                mask_x |= (bounds["x_min"] <= x_max) & (bounds["x_max"] >= x_min)

            # Y-Axis Check
            mask_y = (
                np.ones(n_segments, dtype=bool)
                if not y_intervals
                else np.zeros(n_segments, dtype=bool)
            )
            for y_min, y_max in y_intervals:
                mask_y |= (bounds["y_min"] <= y_max) & (bounds["y_max"] >= y_min)

            expanded_mask = np.repeat(mask_x & mask_y, 3)

            # Retrieve graphics object buffer
            graphic = self.graphics[cp_type]
            if hasattr(graphic, "world_object"):
                buf = graphic.world_object.geometry.positions
            elif hasattr(graphic, "graphics"):
                buf = graphic.graphics[0].world_object.geometry.positions
            else:
                continue

            # IN-PLACE UPDATE: Avoids copying the entire array to a new memory address
            np.copyto(buf.data, base_pos)
            buf.data[~expanded_mask, :] = np.nan
            buf.update_range()
