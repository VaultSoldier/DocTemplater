import logging

import flet as ft

from ui.settings import Settings
from ui.tabs.document import TabEditDocument
from ui.tabs.questions import TabEditQuestions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DocTemplater:
    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self.page: ft.Page = page

    def init_ui(self):
        text_tab_document = ft.Text("Данные документа")
        text_tab_questions = ft.Text("Списки вопросов")
        text_tab_settings = ft.Text("Настройки")

        tab_edit_document = TabEditDocument(self.page)
        tab_edit_questions = TabEditQuestions(self.page)
        settings = Settings(self.page)

        tab_view = ft.TabBarView(
            expand=True,
            controls=[
                tab_edit_document.get_tab_ui(),
                tab_edit_questions.get_tab_ui(),
            ],
        )

        tab_bar = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                # Centered
                ft.TabBar(
                    expand=True,
                    scrollable=False,
                    tabs=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.EDIT_DOCUMENT),
                                text_tab_document,
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[ft.Icon(ft.Icons.NOTES), text_tab_questions],
                        ),
                    ],
                ),
                # Right pinned
                ft.Row(
                    margin=ft.Margin(left=4, top=0, right=6, bottom=0),
                    controls=[
                        ft.IconButton(
                            ft.Icons.SETTINGS,
                            on_click = settings.show
                        ),
                    ],
                ),
            ],
        )

        main_ui = ft.Tabs(
            margin=0,
            length=2,
            expand=True,
            selected_index=0,
            animation_duration=50,
            content=ft.Column(spacing=0, controls=[tab_bar, tab_view]),
        )

        def on_resize(e: ft.PageResizeEvent):
            width = e.width
            height = e.height

            if not height or not width:
                return

            # date_row dropdown's height
            tab_edit_document.date_row.on_resize_change_height(height)

            # Alert table width
            tab_edit_questions.dialog_content_edit_questions.width = width * 0.75

            # Hide tab label
            if width < 575:
                text_tab_document.visible = False
                text_tab_questions.visible = False
                text_tab_settings.visible = False
            else:
                text_tab_document.visible = True
                text_tab_questions.visible = True
                text_tab_settings.visible = True
            self.page.update()

        self.page.on_resize = on_resize

        return main_ui


def main(page: ft.Page):
    page.title = "DocTemplater"
    page.window.icon = "Logo.ico"
    page.padding = 0
    page.window.min_width = 300
    page.window.min_height = 400
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("ru")],
        current_locale=ft.Locale("ru"),
    )

    doc_templater = DocTemplater(page)
    app = doc_templater.init_ui()
    page.add(app)


if __name__ == "__main__":
    from core.processing.data import InitDatabase

    init_db = InitDatabase()
    ft.run(main=main, assets_dir="assets")
