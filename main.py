import logging
from typing import List

import flet as ft

from core.processing.data import AppSettings, InitDatabase
from core.types import AppEvent
from core.ui import load_theme
from ui.settings import Settings
from ui.tabs.document import TabEditDocument
from ui.tabs.questions import TabEditQuestions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DocTemplater:
    def __init__(self, page: ft.Page, init_database: InitDatabase) -> None:
        super().__init__()
        self.page: ft.Page = page
        self.init_database = init_database
        self.tab_edit_document = TabEditDocument(self.page)
        self.tab_edit_questions = TabEditQuestions(self.page)
        self.text_tab_document = ft.Text("Данные документа")
        self.text_tab_questions = ft.Text("Списки вопросов")

    def apply_resize(
        self,
        width: float | None,
        height: float | None,
        text_to_toggle: List[ft.Text],
    ):
        if not height or not width:
            return

        dropdown_height = height * 0.45

        self.tab_edit_document.on_resize_change_dropdowns_height(dropdown_height)
        self.tab_edit_document.date_row.on_resize_change_height(dropdown_height)
        self.tab_edit_questions.dialog_content_edit_questions.width = width * 0.90
        self.tab_edit_questions.dialog_content_tables.width = width * 0.90

        if width < 575:
            for i in text_to_toggle:
                i.visible = False
        else:
            for i in text_to_toggle:
                i.visible = True
        self.page.update()

    def _init(self):
        def on_pubsub(topic):
            if topic == AppEvent.UPDATE_THEME:
                load_theme(button_theme, self.page, data_app_settings)
                self.page.update()

        self.page.pubsub.subscribe(on_pubsub)

        app_settings = Settings(self.page, self.init_database.last_status)
        data_app_settings = AppSettings()
        button_theme = ft.IconButton()

        def switch_theme(e: ft.Event[ft.IconButton]):
            match self.page.theme_mode:
                case ft.ThemeMode.SYSTEM:
                    self.page.theme_mode = ft.ThemeMode.LIGHT
                    e.control.icon = ft.Icons.LIGHT_MODE
                    data_app_settings.save(theme_mode="light")
                case ft.ThemeMode.LIGHT:
                    self.page.theme_mode = ft.ThemeMode.DARK
                    e.control.icon = ft.Icons.DARK_MODE
                    data_app_settings.save(theme_mode="dark")
                case _:
                    self.page.theme_mode = ft.ThemeMode.SYSTEM
                    e.control.icon = ft.Icons.BRIGHTNESS_AUTO
                    data_app_settings.save(theme_mode="system")
            self.page.update()

        button_theme.on_click = switch_theme

        tab_view = ft.TabBarView(
            expand=True,
            controls=[
                self.tab_edit_document.get_ui(),
                self.tab_edit_questions.get_ui(),
            ],
        )

        load_theme(button_theme, self.page, data_app_settings)
        button_settings = ft.IconButton(ft.Icons.SETTINGS, on_click=app_settings.show)

        tab_bar = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
        tab_bar.controls = [
            # Centered
            ft.TabBar(
                expand=True,
                scrollable=False,
                tabs=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.EDIT_DOCUMENT),
                            self.text_tab_document,
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[ft.Icon(ft.Icons.NOTES), self.text_tab_questions],
                    ),
                ],
            ),
            # Right pinned
            ft.Container(
                padding=5,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                content=ft.Row(
                    margin=ft.Margin(left=4, top=0, right=6, bottom=0),
                    controls=[button_theme, button_settings],
                ),
            ),
        ]

        main_ui = ft.Tabs(
            margin=0,
            length=2,
            expand=True,
            selected_index=0,
            animation_duration=50,
            content=ft.Column(spacing=0, controls=[tab_bar, tab_view]),
        )

        def on_resize(e: ft.PageResizeEvent):
            self.apply_resize(
                e.width,
                e.height,
                text_to_toggle=[
                    self.text_tab_document,
                    self.text_tab_questions,
                ],
            )

        self.page.on_resize = on_resize

        return main_ui


def main(page: ft.Page):
    init_database = InitDatabase(page)
    init_database._init()

    page.title = "DocTemplater"
    page.window.icon = "Logo.ico"
    page.padding = 0
    page.window.min_width = 350
    page.window.min_height = 400
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("ru")],
        current_locale=ft.Locale("ru"),
    )

    doc_templater = DocTemplater(page, init_database)
    app = doc_templater._init()
    page.add(app)

    doc_templater.apply_resize(
        page.width,
        page.height,
        text_to_toggle=[
            doc_templater.text_tab_document,
            doc_templater.text_tab_questions,
        ],
    )


if __name__ == "__main__":
    ft.run(main=main, assets_dir="assets")
