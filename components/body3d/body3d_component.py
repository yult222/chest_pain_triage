from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components


# Set to False if you want to run the frontend dev server (vite) locally.
_RELEASE = True

if _RELEASE:
    _component_func = components.declare_component(
        "body3d",
        path=str(Path(__file__).parent / "frontend" / "dist"),
    )
else:
    _component_func = components.declare_component(
        "body3d",
        url="http://localhost:5173",
    )


def body3d_selector(height: int = 420, key: Optional[str] = None) -> Optional[str]:
    """Return the clicked body region name (string) or None."""
    return _component_func(height=height, key=key, default=None)
