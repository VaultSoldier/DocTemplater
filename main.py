import logging

import flet as ft

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

        tab_edit_document = TabEditDocument(self.page)
        tab_edit_questions = TabEditQuestions(self.page)

        tab_bar = ft.TabBar(
            label_text_style=ft.TextStyle(size=14),
            scrollable=False,
            divider_height=1,
            margin=0,
            tabs=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tooltip=text_tab_document.value,
                    controls=[
                        ft.Icon(ft.Icons.EDIT_DOCUMENT),
                        text_tab_document,
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tooltip=text_tab_questions.value,
                    controls=[
                        ft.Icon(ft.Icons.NOTES),
                        text_tab_questions,
                    ],
                ),
            ],
        )

        tab_bar_view = ft.TabBarView(
            margin=0,
            expand=True,
            controls=[
                tab_edit_document.get_tab_ui(),
                tab_edit_questions.get_tab_ui(),
            ],
        )
        tabs = ft.Tabs(
            margin=0,
            length=2,
            expand=True,
            selected_index=0,
            animation_duration=50,
            content=ft.Column(spacing=0, controls=[tab_bar, tab_bar_view]),
        )

        def on_resize(e: ft.PageResizeEvent):
            width = e.width
            height = e.height

            if not height or not width:
                return

            # Alert table width
            tab_edit_questions.dialog_content_edit_questions.width = width * 0.75

            # Hide tab label
            if width < 575:
                text_tab_document.visible = False
                text_tab_questions.visible = False
            else:
                text_tab_document.visible = True
                text_tab_questions.visible = True
            self.page.update()

        self.page.on_resize = on_resize

        return tabs


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
    ft.run(main=main, assets_dir="assets")
