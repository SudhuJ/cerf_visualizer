import numpy as np
import pandas as pd


class CerfDataParser:
    def __init__(self, default_vertex_coords=(0.0, 0.0, 0.0)):
        self.default_coords = default_vertex_coords
        self.data = None

        # Standard colors
        self.color_map = {
            0: [0.0, 0.0, 1.0, 1.0],  # Minima
            1: [0.0, 1.0, 0.0, 1.0],  # Saddle
            2: [1.0, 0.0, 0.0, 1.0],  # Maxima
            3: [0.5, 0.5, 0.5, 1.0],  # Unknown
        }

    def load_and_process(self, filepath):
        df = pd.read_csv(filepath, sep=r"\s+", header=None, engine="c")
        df = df.drop_duplicates().reset_index(drop=True)
        self.data = df.to_numpy()

        num_rows = len(df)

        # 1. Extract positions with a NaN separator
        # Shape: (N lines, 3 points per line [start, end, NaN], 3 coords)
        positions = np.empty((num_rows, 3, 3), dtype=np.float32)

        # Start points (X1, Y1, Z)
        positions[:, 0, 0] = df[0].values  # Start Time
        positions[:, 0, 1] = df[1].values  # Start Function Value
        positions[:, 0, 2] = 0.0

        # End points (X2, Y2, Z)
        positions[:, 1, 0] = df[2].values  # End Time
        positions[:, 1, 1] = df[3].values  # End Function Value
        positions[:, 1, 2] = 0.0

        # NaN Separators to break the continuous line in fastplotlib
        positions[:, 2, :] = np.nan

        # Flatten down to (N*3, 3) for a single massive draw call
        positions = positions.reshape(-1, 3)

        # 2. Extract metadata (x, y, z, cp_type, vertex_id)
        metadata = np.zeros((num_rows, 5), dtype=np.float32)

        # Handle X, Y, Z if they exist (9 column format), otherwise default
        if df.shape[1] >= 9:
            metadata[:, 0] = df.iloc[:, -3].values
            metadata[:, 1] = df.iloc[:, -2].values
            metadata[:, 2] = df.iloc[:, -1].values
        else:
            metadata[:, 0:3] = self.default_coords

        # cp_type is col 4
        cp_types = df[4].fillna(3).astype(int).values
        metadata[:, 3] = cp_types

        # vertex_id is col 5
        metadata[:, 4] = df[5].fillna(-1).values

        # 3. Vectorized Color Mapping
        base_colors = np.full((num_rows, 4), self.color_map[3], dtype=np.float32)
        base_colors[cp_types == 0] = self.color_map[0]
        base_colors[cp_types == 1] = self.color_map[1]
        base_colors[cp_types == 2] = self.color_map[2]

        # Expand colors to match the positions shape (N, 3 points, 4 channels)
        colors = np.empty((num_rows, 3, 4), dtype=np.float32)
        colors[:, 0, :] = base_colors  # Color for start point
        colors[:, 1, :] = base_colors  # Color for end point
        colors[:, 2, :] = base_colors  # Filler for NaN point

        # Flatten to (N*3, 4)
        colors = colors.reshape(-1, 4)

        return positions, colors, metadata

    def save_data(self, filepath: str):
        if self.data is not None:
            np.savetxt(filepath, self.data, fmt="%.6f")
            print(f"Successfully exported to {filepath}")
        else:
            print("No data available to save. Please load a file first.")
