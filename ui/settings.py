import threading

import flet as ft

from core.processing.data import AppSettings, InitDatabase
from core.types import AppEvent
from ui.templates import StyledAlertDialog, StyledButton, StyledTextField


class Settings:
    def __init__(self, page: ft.Page, last_status) -> None:
        self.page = page
        self.last_status = last_status
        self.debounce_timer = None
        self.init_database = InitDatabase(page)
        self.app_settings = AppSettings()

        self.progress_ring = ft.ProgressRing(width=24, height=24)
        self.container_api_status = ft.Container(None, expand=False)

        self.page.pubsub.subscribe(self.on_status_change)

    def on_status_change(self, topic):
        match topic:
            case AppEvent.API_NO_URL:
                self.container_api_status.content = ft.Icon(
                    ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_ACCENT
                )
                self.container_api_status.update()
            case AppEvent.API_ERROR:
                self.container_api_status.content = ft.Icon(
                    ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_ACCENT
                )
                self.container_api_status.update()
            case AppEvent.API_SYNCED:
                self.container_api_status.content = ft.Icon(
                    ft.Icons.CLOUD_DONE, color=ft.Colors.LIGHT_GREEN
                )
                self.container_api_status.update()

    def show(self):
        dialog = StyledAlertDialog(
            actions_padding=ft.Padding.only(left=14, right=14, top=12, bottom=14),
            modal=True,
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
            def debounce_run(api_base: str):
                api_base = "".join(api_base.split())
                if not api_base.startswith(("http://", "https://")):
                    api_base = f"https://{api_base}"

                self.app_settings.save(api_base=api_base)
                self.init_database._sync_all()

            def api_url_save(e: ft.Event[ft.TextField]):
                if self.debounce_timer is not None:
                    self.debounce_timer.cancel()

                self.container_api_status.content = self.progress_ring
                self.debounce_timer = threading.Timer(
                    interval=1.5,
                    function=lambda: debounce_run(api_base=e.control.value),
                )
                self.debounce_timer.start()

            textfield_api = StyledTextField(
                value=self.app_settings.load().get("api_base"),
                label="API URL",
                hint_text="https://example.com:443",
                dense=True,
                expand=True,
                on_change=api_url_save,
            )
            button_sync = StyledButton(
                tooltip="Ручная синхронизация",
                icon=ft.Icons.SYNC,
                content=ft.Text(
                    value="Синхронизировать",
                    overflow=ft.TextOverflow.FADE,
                    no_wrap=True,
                ),
                on_click=self.init_database._sync_all,
            )

            def reset_db(e: ft.Event[ft.Button]):
                textfield_api.value = ""
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
                                ft.Row([textfield_api, self.container_api_status]),
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
        self.on_status_change(self.last_status)
