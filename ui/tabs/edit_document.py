import datetime as dt
import logging

import flet as ft
from anyio import Path

from app_logic import MainUi
from app_logic.processing.docx_creation import Processing
from app_logic.types import QuestionType
from app_logic.ui import open_file
from ui.templates import (
    DateRow,
    Overlay,
    StyledAlertDialog,
    StyledButton,
    StyledSegmentedButton,
    StyledTextField,
    WarnPopup,
)
import locale

locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")


class TabEditDocument(MainUi):
    def __init__(self, page: ft.Page, tab_label: ft.Text) -> None:
        self.tab_label = tab_label
        self.doc_processing = Processing()
        self.page = page

        self.textfield_subject = StyledTextField(
            label="Предмет", max_length=180, on_change=self.on_change_validate
        )
        self.textfield_spec = StyledTextField(
            label="Специальность", max_length=180, on_change=self.on_change_validate
        )
        self.textfield_cmk = StyledTextField(
            label="Председатель ЦМK", max_length=180, on_change=self.on_change_validate
        )
        self.textfield_ticket_number = StyledTextField(
            label="Количество билетов",
            on_change=self.on_change_validate,
            max_length=3,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            # border=ft.InputBorder.UNDERLINE,
            expand=True,
            dense=True,
        )
        self.textfield_tutor = StyledTextField(
            label="Преподаватель", on_change=self.on_change_validate, expand=True
        )

        self.checkbox_qualifying = ft.Checkbox(label="Квалификационные билеты")

        year = dt.date.today().year
        self.date_picker = ft.DatePicker(
            first_date=dt.date(year - 20, 1, 1),
            last_date=dt.date(year + 2, 12, 31),
            on_change=self.on_change_date_picker,
        )
        page.overlay.append(self.date_picker)

        self.date_row = DateRow(
            page=page,
            date_picker=self.date_picker,
            on_change=self.on_change_date_row,
        )

        overlay = Overlay(text_value="Сохрани документ...")
        filepicker = ft.FilePicker(on_result=lambda e: self.on_pick(e, overlay))
        page.overlay.extend([overlay, filepicker])

        self.button_submit = StyledButton(
            text="Создать билет(ы)",
            disabled=True,
            on_click=lambda e: self.on_click_button_submit(e, filepicker, overlay),
        )
        self.button_clear = StyledButton(text="Очистить поля")

        self.segmented_button_ticket_num = StyledSegmentedButton(
            selected={"Manual"}, expand=True
        )
        self.segmented_btn_theoretical = StyledSegmentedButton(
            expand=True, selected={"none"}
        )
        self.segmented_btn_practical = StyledSegmentedButton(
            expand=True, selected={"none"}
        )

    # TODO: IMPLEMENT DATEPICKER CHANGE DATE ON DATEROW UPDATE
    def on_change_date_row(self, e):
        pass

    def on_change_date_picker(self, e):
        date = e.control.value
        formatted = f"{date.year}.{date.strftime('%B')}.{date.day}".split(".")
        print(formatted)
        self.date_row.value = formatted
        self.page.update()

    def _textfield_clear(self, e):
        for field in (
            self.textfield_cmk,
            self.textfield_spec,
            self.textfield_subject,
            self.textfield_tutor,
            self.textfield_ticket_number,
        ):
            field.value = ""
        self.page.update()

    def on_click_button_submit(
        self, e, filepicker: ft.FilePicker, overlay: ft.Container
    ):
        overlay.visible = True
        self.page.update()

        space = ""
        if self.textfield_spec.value:
            space = " по "

        filepicker.save_file(
            dialog_title="Сохранить файл",
            allowed_extensions=["docx"],
            file_name=f"Билеты промежуточной аттестации{space}{self.textfield_spec.value}.docx",
        )

    def on_change_validate(
        self,
        e: ft.ControlEvent,
    ):
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

        self.button_submit.disabled = status
        self.button_submit.update()

    def on_pick(self, e: ft.FilePickerResultEvent, overlay: ft.Container):
        if not e.path:
            overlay.visible = False
            self.page.update()
            logging.info(f"Save path is None: {e.path}")
            return

        filepath: str = e.path
        if filepath[-5:].lower() != ".docx":
            filepath = f"{filepath}.docx"

        text = ft.Text(
            "Документ создается...",
            size=32,
            color="white",
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        loading_ui = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        loading_ui.controls = [text, ft.ProgressRing()]

        def thread():
            overlay.content = loading_ui
            overlay.visible = True
            self.page.update()

            if (
                not self.segmented_btn_theoretical.selected
                or not self.segmented_btn_practical.selected
                or not self.segmented_button_ticket_num.selected
            ):
                return

            status_ticket_number = str(
                next(iter(self.segmented_button_ticket_num.selected))
            )
            status_rnd_practical = str(
                next(iter(self.segmented_btn_practical.selected))
            )
            status_rnd_theoretical = str(
                next(iter(self.segmented_btn_theoretical.selected))
            )

            num_of_tickets = None

            if self.textfield_ticket_number.value:
                num_of_tickets = int(self.textfield_ticket_number.value)

            response = self.doc_processing.generate_document(
                save_to=filepath,
                subject=(self.textfield_subject.value or ""),
                spec=(self.textfield_spec.value or ""),
                cmk=(self.textfield_cmk.value or ""),
                tutor=(self.textfield_tutor.value or ""),
                date=(self.date_row.value),
                qualify_status=self.checkbox_qualifying.value,
                num_of_tickets=num_of_tickets,
                status_cards_number=status_ticket_number,
                status_rnd_practical=status_rnd_practical,
                status_rnd_theoretical=status_rnd_theoretical,
            )
            if response is not None:
                overlay.visible = False
                overlay.update()
                self.page.open(WarnPopup(response))
                return

            self.handle_generation_complete(filepath, overlay)

            overlay.content = Overlay().content

        self.page.run_thread(thread)

    def handle_generation_complete(self, filepath: str, overlay: ft.Container):
        overlay.visible = False
        self.page.update()

        dialog = StyledAlertDialog(
            title=ft.Text("Документ создан", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment(0, 0),
        )
        responsive_row = ft.ResponsiveRow()
        responsive_row.controls = [
            StyledButton(
                text="Открыть файл",
                expand=True,
                on_click=lambda e: open_file(filepath),
            ),
            StyledButton(
                text="Открыть папку",
                on_click=lambda e: open_file(str(Path(filepath).parent)),
            ),
            StyledButton(
                text="Закрыть",
                expand=True,
                on_click=lambda _: self.page.close(dialog),
            ),
        ]
        dialog.actions = [responsive_row]
        self.page.open(dialog)

    def get_tab_ui(self) -> ft.Tab:
        self.button_clear.on_click = self._textfield_clear

        def on_segmented_change(e: ft.ControlEvent):
            if e.control.selected != {"Manual"}:
                self.textfield_ticket_number.disabled = True
                self.textfield_ticket_number.update()
                self.on_change_validate(e)
                return

            self.textfield_ticket_number.disabled = False
            self.textfield_ticket_number.update()
            self.on_change_validate(e)

        self.segmented_button_ticket_num.on_change = on_segmented_change
        self.segmented_button_ticket_num.segments = [
            ft.Segment(
                value="Manual",
                label=ft.Text("Ввод"),
                expand=True,
            ),
            ft.Segment(
                value="Practical", label=ft.Text("Из практических"), expand=True
            ),
            ft.Segment(
                value="Theoretical", label=ft.Text("Из теоретических"), expand=True
            ),
        ]

        def card_questions_num(label: str) -> ft.Card:
            return ft.Card(
                content=ft.Container(
                    padding=20,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.Text(label, weight=ft.FontWeight.BOLD, size=18),
                            self.segmented_button_ticket_num,
                            self.textfield_ticket_number,
                        ],
                    ),
                ),
            )

        number_of_questions = ft.Container()
        number_of_questions.content = ft.Column(
            controls=[
                card_questions_num("Количество билетов"),
            ]
        )

        # INFO: ДОРАБОТАТЬ
        def rnd_card(question_type: QuestionType) -> ft.Card:
            if question_type == QuestionType.PRACTICAL:
                label = "Рандомизация теоретических вопросов"
                segmented_btn = self.segmented_btn_practical
            else:
                label = "Рандомизация практических вопросов"
                segmented_btn = self.segmented_btn_theoretical

            segmented_btn.segments = [
                ft.Segment(
                    value="none",
                    icon=ft.Icon("CLOSE"),
                    label=ft.Text("Не рандомизировать"),
                    expand=True,
                ),
                ft.Segment(
                    value="always",
                    icon=ft.Icon("SHUFFLE"),
                    label=ft.Text("Рандомизировать"),
                    expand=True,
                ),
                ft.Segment(
                    value="fallback",
                    icon=ft.Icon("ROTATE_LEFT"),
                    label=ft.Text("Когда не хватает"),
                    tooltip="По порядку, а если не хватает — рандомизировать",
                    expand=True,
                ),
            ]

            return ft.Card(
                content=ft.Container(
                    padding=20,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.Text(label, weight=ft.FontWeight.BOLD, size=18),
                            segmented_btn,
                        ],
                    ),
                ),
            )

        responsive_row_rnd = ft.ResponsiveRow(
            spacing=5,
            expand=True,
            controls=[
                ft.Column(
                    col={"xs": 12, "sm": 6},
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[rnd_card(QuestionType.PRACTICAL)],
                ),
                ft.Column(
                    col={"xs": 12, "sm": 6},
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[rnd_card(QuestionType.THEORETICAL)],
                ),
            ],
        )

        responsive_row_textfields = ft.ResponsiveRow(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
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
                padding=20,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[responsive_row_textfields],
                ),
            )
        )

        tab_listview = ft.ListView(
            controls=[
                card_textfields,
                number_of_questions,
                responsive_row_rnd,
            ],
            expand=True,
            spacing=10,
        )
        tab_buttons = ft.Container(
            margin=ft.margin.only(left=9, top=0, right=9, bottom=9),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
                controls=[
                    self.button_submit,
                    self.button_clear,
                ],
            ),
        )

        tab = ft.Tab()
        tab.tab_content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(name=ft.Icons.EDIT_DOCUMENT, tooltip=self.tab_label.value),
                self.tab_label,
            ],
        )
        tab.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[ft.Container(tab_listview, expand=1, padding=10), tab_buttons],
        )
        return tab
