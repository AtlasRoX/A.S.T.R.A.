"""NASA data port: manifest + fixtures, read by ASTRA Core.

The engine never makes a network call. Fetch scripts under `scripts/fetch/` pull NASA data on
Earth and commit the result as small fixtures under `engine/data/nasa/`. This package is the
only way the rest of the app reads them.
"""

from .registry import Registry, RegistryError, default_data_dir, load

__all__ = ["Registry", "RegistryError", "default_data_dir", "load"]
