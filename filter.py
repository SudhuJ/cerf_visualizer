import numpy as np


class GPUFilterManager:
    """
    Manages WebGPU-optimized geometry filtering for pygfx/fastplotlib objects
    by utilizing Vertex Shader NaN discarding.
    """

    def __init__(self, graphic, base_positions, metadata):
        self.graphic = graphic
        # Keep a canonical copy of the original positions (N*3, 3) in RAM
        self.base_positions = base_positions.copy()
        self.metadata = metadata
        self.n_segments = len(metadata)

        # Dictionary of active filters (True = visible, False = transparent)
        self.active_filters = {}

    def set_filter(self, filter_name: str, boolean_mask: np.ndarray):
        """Adds or updates a filter and pushes changes to the GPU."""
        self.active_filters[filter_name] = boolean_mask
        self._apply_filters()

    def remove_filter(self, filter_name: str):
        """Removes a specific filter and pushes changes to the GPU."""
        if filter_name in self.active_filters:
            del self.active_filters[filter_name]
            self._apply_filters()

    def clear_all(self):
        """Clears all filters, making everything visible."""
        self.active_filters.clear()
        self._apply_filters()

    def _apply_filters(self):
        # 1. Base state: Everything is visible
        global_mask = np.ones(self.n_segments, dtype=bool)

        # 2. Intersect all active filters
        for mask in self.active_filters.values():
            global_mask &= mask

        # 3. Expand mask from (N) to (N*3) to match the Start-End-NaN vertex structure
        expanded_mask = np.repeat(global_mask, 3)

        # 4. Generate new buffer data (set coordinates to NaN for hidden segments)
        new_positions = self.base_positions.copy()
        new_positions[~expanded_mask, :] = np.nan

        # --- BLEEDING EDGE GPU OPTIMIZATION ---
        # By bypassing standard fastplotlib wrappers and hitting the pygfx buffer directly,
        # wgpu performs a direct memory-mapped write to VRAM. Zero pipeline rebuilds.
        pygfx_pos_buffer = self.graphic.world_object.geometry.positions
        pygfx_pos_buffer.data[:] = new_positions
        pygfx_pos_buffer.update_range()
