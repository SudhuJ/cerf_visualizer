import numpy as np
import pandas as pd


class CerfDataParser:
    def __init__(self, default_vertex_coords=(0.0, 0.0, 0.0)):
        self.default_coords = default_vertex_coords
        self.data = None

        # Standard colors mapped as strict Uniform Tuples (R, G, B, Alpha)
        self.color_map = {
            0: (0.0, 0.0, 1.0, 0.9),  # Minima: Smooth Azure Blue
            1: (0.0, 1.0, 0.0, 0.9),  # Saddle: Vibrant Emerald Green
            2: (1, 0.0, 0.0, 0.9),  # Maxima: Soft Crimson Red
            3: (0.40, 0.40, 0.40, 0.9),  # Unknown: Faint Ghost Grey
        }

    def load_and_process(self, filepath):
        df = pd.read_csv(filepath, sep=r"\s+", header=None, engine="c")
        df = df.drop_duplicates().reset_index(drop=True)
        self.data = df.to_numpy()

        # cp_type is col 4
        cp_types = df[4].fillna(3).astype(int).values

        # Store separated arrays
        positions_by_type = {}
        metadata_by_type = {}

        for cp_type in [0, 1, 2, 3]:
            # Filter dataframe by type
            mask = cp_types == cp_type
            df_subset = df[mask]

            num_rows = len(df_subset)
            if num_rows == 0:
                continue

            # Extract positions with NaN separators
            positions = np.empty((num_rows, 3, 3), dtype=np.float32)

            positions[:, 0, 0] = df_subset[0].values
            positions[:, 0, 1] = df_subset[1].values
            positions[:, 0, 2] = 0.0

            positions[:, 1, 0] = df_subset[2].values
            positions[:, 1, 1] = df_subset[3].values
            positions[:, 1, 2] = 0.0

            positions[:, 2, :] = np.nan

            positions_by_type[cp_type] = positions.reshape(-1, 3)

            # Extract localized metadata (Ensures click events index correctly)
            metadata_subset = np.zeros((num_rows, 5), dtype=np.float32)
            if df_subset.shape[1] >= 9:
                metadata_subset[:, 0] = df_subset.iloc[:, -3].values
                metadata_subset[:, 1] = df_subset.iloc[:, -2].values
                metadata_subset[:, 2] = df_subset.iloc[:, -1].values
            else:
                metadata_subset[:, 0:3] = self.default_coords

            metadata_subset[:, 3] = cp_type
            metadata_subset[:, 4] = df_subset[5].fillna(-1).values

            metadata_by_type[cp_type] = metadata_subset

        return positions_by_type, metadata_by_type

    def save_data(self, filepath: str):
        if self.data is not None:
            np.savetxt(filepath, self.data, fmt="%.6f")
            print(f"Successfully exported to {filepath}")
        else:
            print("No data available to save. Please load a file first.")
