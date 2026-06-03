# CERF Visualizer

A high-performance visualizer for CERF (Critical Element/Response Function) diagrams using WebGPU-accelerated graphics.

## Prerequisites

- **Python 3.10+** (Recommended)
The following packages are required:
```
pip install numpy pandas fastplotlib imgui-bundle pygfx pillow rendercanvas
```

## Installation

1. Clone this repository to your local machine.

2. Navigate to the project directory:
   ```bash
   cd cerf_visualizer


## Usage  

Note that the following CERF input is expected currently. Each line in the .txt file represents 1 line segment.

`<time_value_1> <function_value_1> <time_value_2> <function_value_2> <critical_point_type> <vertex_ID>`
