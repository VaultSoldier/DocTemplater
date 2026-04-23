import flet as ft

from core.processing.data import InitDatabase
from core.types import AppEvent
from ui.templates import StyledAlertDialog, StyledButton, StyledTextField


class Settings:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.init_database = InitDatabase()

    def show(self):
        dialog = StyledAlertDialog(
            modal=True,
            actions_padding=ft.Padding.only(left=14, right=14, top=12, bottom=14),
        )
        button_close = StyledButton(
            tooltip="Закрыть",
            icon=ft.Icons.CLOSE,
            content=ft.Text(
                value="Закрыть",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            on_click=self.page.pop_dialog,
        )

        def section_data():
            textfield_api = StyledTextField(
                label="API URL",
                hint_text="https://example.com:443",
                dense=True,
                expand=True,
            )
            button_sync = StyledButton(
                tooltip="Ручная синхронизация",
                icon=ft.Icons.SYNC,
                content=ft.Text(
                    value="Синхронизировать",
                    overflow=ft.TextOverflow.FADE,
                    no_wrap=True,
                ),
                # on_click=
            )

            def reset_db(e: ft.Event[ft.Button]):
                self.init_database.reset_db()
                self.page.pubsub.send_all(AppEvent.UPDATE_THEME)
                self.page.pubsub.send_all(AppEvent.DB_RESET)

            button_rest_db = StyledButton(
                icon=ft.Icons.LOCK_RESET,
                content=ft.Text(
                    value="Сброс БД",
                    overflow=ft.TextOverflow.FADE,
                    no_wrap=True,
                ),
                on_click=reset_db,
            )

            controls = [
                ft.Text(
                    value="Данные",
                    margin=ft.Margin.only(left=9),
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD,
                    size=24,
                ),
                ft.Card(
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            tight=True,
                            controls=[
                                ft.Row([textfield_api]),
                                ft.Row([button_sync, button_rest_db]),
                            ],
                        ),
                    ),
                ),
            ]
            return controls

        dialog.content = ft.Column(tight=True, controls=[*section_data()])
        dialog.actions = [ft.Row(controls=[button_close])]
        self.page.show_dialog(dialog)
