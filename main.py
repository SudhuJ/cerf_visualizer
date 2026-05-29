from visualizer import CerfVisualizer

if __name__ == "__main__":
    filepath = "20-33_Cerf_5_115.txt"

    print("Initializing CERF visualizer pipeline.")
    app = CerfVisualizer(filepath)
    app.show()
