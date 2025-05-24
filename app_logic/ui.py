import platform
import os
import subprocess
import logging
import flet as ft
from ui.templates import DateRow


class MainUi:
    def __init__(self) -> None:
        super().__init__()

    def on_resize(
        self,
        e,
        date_row: DateRow,
        page: ft.Page,
        label_document_edit: ft.Text,
        label_questions_list: ft.Text,
    ):
        width = page.width
        height = page.height

        if not height or not width:
            return

        date_row.on_resize_change_height(height)

        if width < 575:
            label_document_edit.visible = False
            label_questions_list.visible = False
        else:
            label_document_edit.visible = True
            label_questions_list.visible = True
        page.update()

    def validate(
        self, e: ft.ControlEvent, page: ft.Page, button: ft.Button, *args: ft.TextField
    ):
        status = not any((arg.value or "").strip() for arg in args)
        button.disabled = status
        page.update()


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
