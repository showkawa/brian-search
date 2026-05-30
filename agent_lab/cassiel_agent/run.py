"""Cassiel Agent — single entry point to launch the app."""

from cassiel.ui.main import run

if __name__ in {"__main__", "__mp_main__"}:
    run()
