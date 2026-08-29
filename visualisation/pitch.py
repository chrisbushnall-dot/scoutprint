from __future__ import annotations

import numpy as np
import plotly.graph_objects as go


def _pitch_shapes() -> list[dict]:
    line = {"color": "rgba(235,245,240,.72)", "width": 1.2}
    return [
        {"type": "rect", "x0": 0, "y0": 0, "x1": 100, "y1": 100, "line": line},
        {"type": "line", "x0": 50, "y0": 0, "x1": 50, "y1": 100, "line": line},
        {"type": "circle", "x0": 41.5, "y0": 36.5, "x1": 58.5, "y1": 63.5, "line": line},
        {"type": "rect", "x0": 0, "y0": 21.1, "x1": 14.17, "y1": 78.9, "line": line},
        {"type": "rect", "x0": 85.83, "y0": 21.1, "x1": 100, "y1": 78.9, "line": line},
        {"type": "rect", "x0": 0, "y0": 36.8, "x1": 5, "y1": 63.2, "line": line},
        {"type": "rect", "x0": 95, "y0": 36.8, "x1": 100, "y1": 63.2, "line": line},
    ]


def heatmap_figure(
    vector: object, grid_x: int, grid_y: int, title: str, difference: bool = False
) -> go.Figure:
    grid = np.asarray(vector, dtype=float).reshape(grid_x, grid_y)
    colors = (
        "RdBu"
        if difference
        else [[0, "#07140f"], [0.25, "#0d5b42"], [0.65, "#46d88c"], [1, "#f1ff79"]]
    )
    bound = float(np.max(np.abs(grid))) if difference and grid.size else None
    figure = go.Figure(
        go.Heatmap(
            z=grid.T,
            x=(np.arange(grid_x) + 0.5) * 100 / grid_x,
            y=(np.arange(grid_y) + 0.5) * 100 / grid_y,
            colorscale=colors,
            zmid=0 if difference else None,
            zmin=-bound if difference else 0,
            zmax=bound if difference else None,
            colorbar={"thickness": 8, "title": "Δ" if difference else "mass"},
            hovertemplate="x=%{x:.0f}, y=%{y:.0f}<br>mass=%{z:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": title, "font": {"size": 15}},
        height=410,
        margin={"l": 8, "r": 8, "t": 45, "b": 8},
        paper_bgcolor="#06100d",
        plot_bgcolor="#0b3225",
        font={"color": "#eaf6f0"},
        shapes=_pitch_shapes(),
        xaxis={"range": [0, 100], "visible": False, "constrain": "domain"},
        yaxis={"range": [100, 0], "visible": False, "scaleanchor": "x", "scaleratio": 0.68},
    )
    return figure
