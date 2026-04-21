import flet as ft

from ui.templates import StyledAlertDialog, StyledButton, StyledTextField


class Settings:
    def __init__(self, page: ft.Page) -> None:
        self.page = page

    def show(self):
        dialog = StyledAlertDialog(
            title=ft.Text("Настройки", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment(0, 0),
            modal=True,
        )
        button_save = StyledButton(
            content=ft.Text(
                value="Сохранить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
        )
        button_close = StyledButton(
            content=ft.Text(
                value="Закрыть",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            on_click=self.page.pop_dialog
        )

        settings = ft.Row(
            spacing=9,
            expand=True,
            controls=[
                ft.ListView(
                    expand=True,
                    controls=[
                        StyledTextField(),
                    ],
                ),
            ],
        )
        buttons = ft.Row(
            margin=ft.Margin.all(9),
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[button_save, button_close],
        )
        dialog.content = ft.Column([settings])
        dialog.actions = [buttons]
        self.page.show_dialog(dialog)
