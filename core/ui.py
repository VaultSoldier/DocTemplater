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
            subprocess.Popen(
                ["open", filepath],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", filepath],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        logging.exception(f"Can't open file: {e}")


def load_theme(icon_button: ft.IconButton, page: ft.Page, app_settings: AppSettings):
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
