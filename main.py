import flet as ft
import logging
from ui.tabs.edit_document import TabEditDocument
from ui.tabs.edit_questions import TabEditQuestions
from app_logic import MainUi

# INFO: MAKE SEPPARATE FILE FOR logging CONFIG
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DocTemplater(MainUi):
    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self.page: ft.Page = page

    def init_ui(self):
        label_edit_document = ft.Text(
            value="Данные документа",
        )
        label_edit_questions = ft.Text(
            value="Списки вопросов",
        )

        tab_edit_document = TabEditDocument(self.page, label_edit_document)
        tab_edit_questions = TabEditQuestions(self.page, label_edit_questions)

        tabs = ft.Tabs(
            label_text_style=ft.TextStyle(size=16),
            selected_index=0,
            animation_duration=80,
            divider_height=1.70,
            scrollable=False,
            expand=True,
            tabs=[
                tab_edit_document.get_tab_ui(),
                tab_edit_questions.get_tab_ui(),
            ],
        )

        self.page.on_resized = lambda e: self.on_resize(
            e,
            tab_edit_document.date_row,
            self.page,
            label_edit_document,
            label_edit_questions,
        )

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
    ft.app(target=main, assets_dir="assets")
