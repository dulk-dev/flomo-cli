"""flomo-cli: Flomo CLI via reverse-engineered API."""

try:
    from importlib.metadata import version

    __version__ = version("flomo-cli")
except Exception:
    __version__ = "0.1.0"
