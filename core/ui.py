import logging
import os
import platform
import subprocess

import flet as ft

from core.processing.data import AppSettings


def open_file(filepath: str):
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)  # type: ignore[reportAttributeAccessIssue]
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        logging.error(f"Can't open file: {e}")


def load_theme(
    icon_button: ft.IconButton, page: ft.Page, app_settings: AppSettings
):
    current_theme = app_settings.load().get("theme_mode", "system")

    theme_map = {
        "light": (ft.ThemeMode.LIGHT, ft.Icons.LIGHT_MODE),
        "dark": (ft.ThemeMode.DARK, ft.Icons.DARK_MODE),
        "system": (ft.ThemeMode.SYSTEM, ft.Icons.BRIGHTNESS_AUTO),
    }

    mode, icon = theme_map.get(
        current_theme, (ft.ThemeMode.SYSTEM, ft.Icons.BRIGHTNESS_AUTO)
    )
    icon_button.icon = icon
    page.theme_mode = mode
