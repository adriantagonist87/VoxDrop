"""Choose the model store without changing the signed application bundle."""

import os
from pathlib import Path


def data_directory(profile, resources):
    if override := os.environ.get("VOXDROP_MODEL_DATA"):
        return Path(override).expanduser().absolute()
    if "VOXDROP_PROFILE" in os.environ:
        return profile / "data"
    app = resources.parent.parent
    if (
        resources.name == "Resources"
        and resources.parent.name == "Contents"
        and app.suffix == ".app"
        and app.parent.name == "VoxDrop"
    ):
        return app.parent / "Modelle"
    return profile / "data"
