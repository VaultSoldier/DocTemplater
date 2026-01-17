import datetime as dt
import locale
import logging

import flet as ft
from anyio import Path

from config import config
from core.processing.docx import DocxProcessingError, Processing
from core.types import QuestionType
from core.ui import open_file
from ui.templates import (
    DateRow,
    Overlay,
    StyledAlertDialog,
    StyledButton,
    StyledSegmentedButton,
    StyledTextField,
    WarnPopup,
)

locale.setlocale(locale.LC_ALL, "")


class TabEditDocument:
    def __init__(self, page: ft.Page) -> None:
        self.docx_processing = Processing()
        self.page = page

        self.textfield_subject = StyledTextField(
            label="Предмет",
            on_change=self.on_change_validate,
            expand=True,
            dense=True,
            max_length=180,
            counter="",
        )
        self.textfield_spec = StyledTextField(
            label="Специальность",
            on_change=self.on_change_validate,
            expand=True,
            dense=True,
            max_length=180,
            counter="",
        )
        self.textfield_cmk = StyledTextField(
            label="Председатель ЦМK",
            on_change=self.on_change_validate,
            expand=True,
            dense=True,
            max_length=180,
            counter="",
        )
        self.textfield_tutor = StyledTextField(
            label="Преподаватель",
            on_change=self.on_change_validate,
            expand=True,
            dense=True,
            max_length=180,
            counter="",
        )

        self.checkbox_qualifying = ft.Checkbox(label="Квалификационные билеты")

        year = dt.date.today().year
        self.date_picker = ft.DatePicker(
            first_date=dt.date(year - 20, 1, 1),
            last_date=dt.date(year + 2, 12, 31),
            on_change=self.on_change_date_picker,
        )
        self.page.overlay.append(self.date_picker)

        self.date_row = DateRow(
            page=self.page,
            date_picker=self.date_picker,
            on_select=self.on_select_date_row,
        )

        self.overlay = Overlay(text_value="Сохрани документ...")
        self.page.overlay.append(self.overlay)

        self.save_file_path = ""
        self.button_create = StyledButton(
            content="Создать билет(ы)",
            disabled=True,
            on_click=self.on_click_button_create,
        )
        self.button_clear_fields = StyledButton(content="Очистить поля")

        self.textfield_ticket_number = StyledTextField(
            label="Количество билетов",
            on_change=self.on_change_validate,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            max_length=3,
            counter="",
            dense=True,
        )

        def on_segmented_change(e):
            if e.control.selected != ["Manual"]:
                self.textfield_ticket_number.disabled = True
                self.textfield_ticket_number.update()
                self.on_change_validate(e)
                return

            self.textfield_ticket_number.disabled = False
            self.textfield_ticket_number.update()
            self.on_change_validate(e)

        self.segmented_button_ticket_num = StyledSegmentedButton(
            on_change=on_segmented_change,
            selected=["Manual"],
            segments=[
                ft.Segment(
                    value="Manual",
                    label=ft.Text(
                        "Ввод",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Ручной ввод",
                ),
                ft.Segment(
                    value="Practical",
                    label=ft.Text(
                        "Из практических",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Сгенерировать столько билетов, сколько практических вопросов.",
                ),
                ft.Segment(
                    value="Theoretical",
                    label=ft.Text(
                        "Из теоретических",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Сгенерировать столько билетов, сколько теоретических вопросов.",
                ),
            ],
        )
        self.segmented_btn_theoretical = StyledSegmentedButton(
            expand=True, selected=["fallback"]
        )
        self.segmented_btn_practical = StyledSegmentedButton(
            expand=True, selected=["fallback"]
        )

    # TODO: IMPLEMENT DATEPICKER CHANGE DATE ON DATEROW UPDATE
    def on_select_date_row(self, e) -> None:
        pass

    def on_change_date_picker(self, e) -> None:
        MONTHS_RU_GEN = [
            "",
            "января",
            "февраля",
            "марта",
            "апреля",
            "мая",
            "июня",
            "июля",
            "августа",
            "сентября",
            "октября",
            "ноября",
            "декабря",
        ]
        date = e.control.value

        formatted = f"{date.year}.{MONTHS_RU_GEN[date.month]}.{date.day}".split(".")
        logging.info(formatted)

        self.date_row.value = formatted
        self.page.update

    def _textfield_clear(self, e) -> None:
        for field in (
            self.textfield_cmk,
            self.textfield_spec,
            self.textfield_subject,
            self.textfield_tutor,
            self.textfield_ticket_number,
        ):
            field.value = ""
        self.page.update

    def on_change_validate(
        self,
        e: ft.ControlEvent,
    ) -> None:
        textfields = (
            self.textfield_subject,
            self.textfield_spec,
            self.textfield_cmk,
            self.textfield_tutor,
        )

        filled_any = any((tf.value or "").strip() for tf in textfields)
        number_ok = bool((self.textfield_ticket_number.value or "").strip())

        if self.textfield_ticket_number.disabled:
            status = not filled_any
        else:
            status = not (filled_any and number_ok)

        self.button_create.disabled = status
        self.button_create.update()

    async def handle_save_file(self) -> str | None:
        space = ""
        if self.textfield_spec.value:
            space = " по "

        return await ft.FilePicker().save_file(
            dialog_title="Сохранить файл",
            allowed_extensions=["docx"],
            file_name=f"Билеты промежуточной аттестации{space}{self.textfield_spec.value}.docx",
        )

    async def on_click_button_create(self, e: ft.Event[ft.Button]) -> None:
        self.overlay.visible = True
        self.overlay.update()
        save_file_path = await self.handle_save_file()

        if not save_file_path:
            self.overlay.visible = False
            self.page.update
            logging.info(f"Save path: {save_file_path}")
            return

        if not save_file_path.lower().endswith(".docx"):
            save_file_path = f"{save_file_path}.docx"

        text = ft.Text(
            "Документ создается...",
            size=32,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        loading_ui = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        loading_ui.controls = [text, ft.ProgressRing()]

        self.overlay.content = loading_ui
        self.overlay.visible = True
        self.page.update

        if (
            not self.segmented_btn_theoretical.selected
            or not self.segmented_btn_practical.selected
            or not self.segmented_button_ticket_num.selected
        ):
            return

        tickets_count_type = str(next(iter(self.segmented_button_ticket_num.selected)))
        practical_rnd_type = str(next(iter(self.segmented_btn_practical.selected)))
        theoretical_rnd_type = str(next(iter(self.segmented_btn_theoretical.selected)))
        tickets_count = None

        if self.textfield_ticket_number.value:
            tickets_count = int(self.textfield_ticket_number.value)

        try:
            response = self.docx_processing.process_docx(
                save_to=save_file_path,
                subject=(self.textfield_subject.value or ""),
                spec=(self.textfield_spec.value or ""),
                cmk=(self.textfield_cmk.value or ""),
                tutor=(self.textfield_tutor.value or ""),
                date=(self.date_row.value),
                qualify_status=self.checkbox_qualifying.value,
                tickets_count=tickets_count,
                tickets_count_type=tickets_count_type,
                practical_rnd_type=practical_rnd_type,
                theoretical_rnd_type=theoretical_rnd_type,
            )
        except DocxProcessingError as error:
            logging.info(f"Error processing docx: {error}'")
            self.hide_overlay(self.overlay)

            self.page.show_dialog(WarnPopup(error))
            return

        self.show_dialog_generation_complete(save_file_path)
        self.hide_overlay(self.overlay)

        if not response:
            return

        self.page.run_thread(
            lambda: self.docx_processing.clean(path=response[0], paths=response[1])
        )

    def hide_overlay(self, overlay: ft.Container) -> None:
        overlay.visible = False
        overlay.update()
        overlay.content = Overlay().content

    def show_dialog_generation_complete(self, filepath: str) -> None:
        dialog = StyledAlertDialog(
            title=ft.Text("Документ создан", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment(0, 0),
        )
        responsive_row = ft.ResponsiveRow()
        responsive_row.controls = [
            StyledButton(
                content="Открыть файл",
                expand=True,
                on_click=lambda e: open_file(filepath),
            ),
            StyledButton(
                content="Открыть папку",
                on_click=lambda e: open_file(str(Path(filepath).parent)),
            ),
            StyledButton(
                content="Закрыть",
                expand=True,
                on_click=self.page.pop_dialog,
            ),
        ]
        dialog.actions = [responsive_row]
        self.page.show_dialog(dialog)

    def get_tab_ui(self) -> ft.Column:
        self.button_clear_fields.on_click = self._textfield_clear

        def get_card_questions() -> ft.Card:
            column = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self.textfield_ticket_number,
                    self.segmented_button_ticket_num,
                ],
            )
            card = ft.Card(
                content=ft.Container(
                    padding=12,
                    content=column,
                )
            )
            return card

        def get_segment_rnd(question_type: QuestionType) -> ft.Container:
            if question_type == QuestionType.PRACTICAL:
                label = "Рандомизация теоретических вопросов"
                segmented_btn = self.segmented_btn_practical
            else:
                label = "Рандомизация практических вопросов"
                segmented_btn = self.segmented_btn_theoretical

            segmented_btn.segments = [
                ft.Segment(
                    value="fallback",
                    icon=ft.Icons.AUTO_AWESOME,
                    label=ft.Text(
                        "Смешанный режим",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Не случайные, если закончились — случайные",
                    expand=True,
                ),
                ft.Segment(
                    value="always",
                    icon=ft.Icons.SHUFFLE,
                    label=ft.Text(
                        "Случайные",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Всегда случайный вопрос",
                    expand=True,
                ),
                ft.Segment(
                    value="none",
                    icon=ft.Icons.CLOSE,
                    label=ft.Text(
                        "Не случайные",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Последовательный, не случайный порядок",
                    expand=True,
                ),
            ]

            card = ft.Container(padding=12)
            card.content = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                margin=0,
                controls=[
                    ft.Text(
                        label,
                        tooltip=label,
                        weight=config.fontweight,
                        size=config.fontsize,
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    segmented_btn,
                ],
            )
            return card

        cards_rnd = ft.ResponsiveRow(
            expand=True,
            run_spacing=0,
            spacing=0,
            controls=[
                ft.Column(
                    expand=True,
                    col={"xs": 12, "sm": 6},
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Card(
                            content=get_segment_rnd(QuestionType.PRACTICAL),
                        )
                    ],
                ),
                ft.Column(
                    expand=True,
                    col={"xs": 12, "sm": 6},
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Card(
                            content=get_segment_rnd(
                                QuestionType.THEORETICAL,
                            ),
                        )
                    ],
                ),
            ],
        )

        responsive_row_textfields = ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            controls=[
                ft.Column(
                    col={"sm": 6},
                    controls=[self.textfield_cmk, self.date_row],
                ),
                ft.Column(
                    col={"sm": 6},
                    controls=[self.textfield_subject, self.textfield_spec],
                ),
                self.textfield_tutor,
                self.checkbox_qualifying,
            ],
        )
        card_textfields = ft.Card(
            content=ft.Container(
                padding=12,
                content=responsive_row_textfields,
            ),
        )

        main_content = ft.Container(
            margin=ft.Margin.all(6),
            expand=True,
            padding=0,
            content=ft.ListView(
                expand=True,
                controls=[
                    card_textfields,
                    get_card_questions(),
                    cards_rnd,
                ],
            ),
        )
        tab_buttons = ft.Container(
            margin=ft.Margin.only(left=9, top=0, right=9, bottom=9),
            content=ft.Row(
                spacing=9,
                expand=True,
                margin=ft.Margin.all(0),
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    self.button_create,
                    self.button_clear_fields,
                ],
            ),
        )

        tab = ft.Column(
            expand=True,
            spacing=0,
            controls=[main_content, tab_buttons],
        )
        return tab
