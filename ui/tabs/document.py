import asyncio
import datetime as dt
import locale
import logging
from typing import List

import flet as ft
from anyio import Path

from config import config
from core.processing.data import SqliteData
from core.processing.docx import DocxProcessingCancel, DocxProcessingError, Processing
from core.types import AppEvent, QuestionType
from core.ui import open_file
from ui.templates import (
    DateRow,
    Overlay,
    OverlayText,
    StyledAlertDialog,
    StyledButton,
    StyledDropdown,
    StyledSegmentedButton,
    StyledTextField,
    WarnPopup,
)

locale.setlocale(locale.LC_ALL, "")


class TabEditDocument:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._uploading = False
        self.save_file_path = ""
        self._subject_id_map: dict[str, int] = {}
        self.page.pubsub.subscribe(self.on_pubsub)
        self.docx_processing = Processing()
        self.sqlite = SqliteData()

        self.dropdown_textfield_subject = StyledDropdown(
            label="Предмет",
            on_select=self._on_subject_select,
            on_text_change=self.on_dropdown_change_validate,
        )

        self.dropdown_textfield_cmk = StyledDropdown(
            label="Председатель ЦМK",
            on_select=self.on_change_validate,
            on_text_change=self.on_dropdown_change_validate,
        )

        self.dropdown_textfield_spec = StyledDropdown(
            label="Специальность",
            on_select=self.on_change_validate,
            on_text_change=self.on_dropdown_change_validate,
        )

        self.dropdown_textfield_tutor = StyledDropdown(
            label="Преподаватель",
            on_select=self.on_change_validate,
            on_text_change=self.on_dropdown_change_validate,
        )

        self.dropdowns = [
            self.dropdown_textfield_spec,
            self.dropdown_textfield_cmk,
            self.dropdown_textfield_tutor,
            self.dropdown_textfield_subject,
        ]

        self.checkbox_qualifying = ft.Checkbox(label="Квалификационные билеты")

        year = dt.date.today().year
        self.date_picker = ft.DatePicker(
            first_date=dt.date(year - 20, 1, 1),
            last_date=dt.date(year + 2, 12, 31),
            on_change=self.on_change_date_picker,
        )
        self.page.overlay.append(self.date_picker)
        self.date_row = DateRow(page=self.page, date_picker=self.date_picker)

        self.button_create = StyledButton(
            tooltip="Создать билет(ы)",
            icon=ft.Icons.QUEUE,
            content=ft.Text(
                value="Создать билет(ы)",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            disabled=True,
            on_click=self.on_click_button_create,
        )
        self.button_clear_fields = StyledButton(
            tooltip="Очистить поля",
            icon=ft.Icons.CLEAR_ALL,
            content=ft.Text(
                value="Очистить поля",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
        )

        self.textfield_ticket_number = StyledTextField(
            hint_text="0",
            on_change=self.on_change_validate,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            max_length=3,
            counter="",
        )

        self.segmented_button_ticket_num = StyledSegmentedButton(
            on_change=self.on_segmented_button_change,
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
                    tooltip="Количество билетов = количество практических вопросов.",
                ),
                ft.Segment(
                    value="Theoretical",
                    label=ft.Text(
                        "Из теоретических",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Количество билетов = количество теоретических вопросов.",
                ),
            ],
        )
        self.segmented_btn_theoretical = StyledSegmentedButton(
            expand=True, selected=["fallback"]
        )
        self.segmented_btn_practical = StyledSegmentedButton(
            expand=True, selected=["fallback"]
        )

        self._populate_static_dropdowns()

    def on_pubsub(self, topic) -> None:
        match topic:
            case AppEvent.DB_RESET | AppEvent.API_SYNCED:
                self._populate_static_dropdowns()
                self.dropdown_textfield_spec.options = []
                self.dropdown_textfield_spec.value = None
                self.dropdown_textfield_spec.text = ""
                self.page.update()
                self.on_change_validate()
            case AppEvent.TABLE_CHANGED:
                self.on_change_validate()

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
        date = e.control.value.astimezone().date()

        formatted = [str(date.year), MONTHS_RU_GEN[date.month], str(date.day)]
        logging.info(formatted)

        self.date_row.value = formatted
        self.page.update()

    def on_resize_change_dropdowns_height(self, height: float):
        for i in self.dropdowns:
            i.menu_height = height
            i.update()

    def _textfield_clear(self, e) -> None:
        for i in self.dropdowns:
            i.value = None
            i.text = ""
        self.textfield_ticket_number.value = ""
        self._populate_spec_options(subject_name=None)
        self.page.update()
        self.on_change_validate()

    def on_segmented_button_change(self, e):
        """Called when ticket type selection changes"""
        qtype = None
        match e.control.selected:
            case ["Practical"]:
                qtype = QuestionType.PRACTICAL
            case ["Theoretical"]:
                qtype = QuestionType.THEORETICAL
            case _:
                self.textfield_ticket_number.disabled = False
                self.textfield_ticket_number.update()
                self.on_change_validate()
                return

        self.textfield_ticket_number.disabled = True
        self.textfield_ticket_number.update()

        if self.sqlite.has_questions(qtype):
            self.on_change_validate()
            return

        match qtype:
            case QuestionType.PRACTICAL:
                self.page.show_dialog(WarnPopup("Нет практических вопросов"))
            case QuestionType.THEORETICAL:
                self.page.show_dialog(WarnPopup("Нет теоретических вопросов"))

        self.on_change_validate()

    def on_dropdown_change_validate(self, e: ft.Event[ft.Dropdown]):
        if e.control.options == []:
            e.control.menu_height = 0
        elif e.control.menu_height == 0:
            e.control.menu_height = None

        e.control.update()
        self.on_change_validate()

    def on_change_validate(self):
        can_enable_button = False
        has_any_text = any((tf.text or "").strip() for tf in self.dropdowns)

        match self.segmented_button_ticket_num.selected:
            case ["Manual"]:
                ticket_number_value = int(self.textfield_ticket_number.value or 0)
                correct_ticket_number: bool = True if ticket_number_value > 0 else False
                can_enable_button = correct_ticket_number and has_any_text
            case ["Practical"]:
                can_enable_button = (
                    self.sqlite.has_questions(QuestionType.PRACTICAL) and has_any_text
                )
            case ["Theoretical"]:
                can_enable_button = (
                    self.sqlite.has_questions(QuestionType.THEORETICAL) and has_any_text
                )

        self.button_create.disabled = not can_enable_button
        self.button_create.update()

    def _populate_static_dropdowns(self) -> None:
        subjects = self.sqlite.read_subjects()
        self._subject_id_map = {name: db_id for db_id, name in subjects}
        self.dropdown_textfield_subject.options = [
            ft.DropdownOption(key=name, text=name) for _, name in subjects
        ]

        cmk = self.sqlite.read_chairman_cmk()
        self.dropdown_textfield_cmk.options = [
            ft.DropdownOption(key=name, text=name) for _, name in cmk
        ]

        teachers = self.sqlite.read_teachers()
        self.dropdown_textfield_tutor.options = [
            ft.DropdownOption(key=name, text=name) for _, name in teachers
        ]

        self._populate_spec_options(subject_name=None)

    def _populate_spec_options(self, subject_name: str | None) -> None:
        """Refill specialty options. Pass None to show all specialties."""
        subject_db_id = self._subject_id_map.get(subject_name or "")

        if subject_db_id is not None:
            specialties = self.sqlite.read_specialties_by_subject(subject_db_id)
        else:
            specialties = self.sqlite.read_all_specialties()

        self.dropdown_textfield_spec.options = [
            ft.DropdownOption(key=name, text=name) for _, name in specialties
        ]

        valid = {name for _, name in specialties}
        if (self.dropdown_textfield_spec.value or "") not in valid:
            self.dropdown_textfield_spec.value = None
            self.dropdown_textfield_spec.text = ""

    def _on_subject_select(self, e=None) -> None:
        selected_name = (e.control.value if e is not None else None) or ""
        self._populate_spec_options(subject_name=selected_name or None)
        self.dropdown_textfield_spec.update()
        self.on_change_validate()

    async def handle_save_file(self) -> str | None:
        text = self.dropdown_textfield_spec.text or ""
        space = " по " if text else ""

        return await ft.FilePicker().save_file(
            dialog_title="Сохранить файл",
            allowed_extensions=["docx"],
            file_name=f"Билеты промежуточной аттестации{space}{text}.docx",
        )

    async def on_click_button_create(self, e: ft.Event[ft.Button]) -> None:
        if self._uploading:
            return
        self._uploading = True

        text_color = ft.Colors.WHITE
        if (
            self.page.theme_mode == ft.ThemeMode.SYSTEM
            and self.page.platform_brightness == ft.Brightness.LIGHT
        ):
            text_color = ft.Colors.GREY_800
        elif self.page.theme_mode == ft.ThemeMode.LIGHT:
            text_color = ft.Colors.GREY_800

        overlay_text = OverlayText("Сохраните документ...", color=text_color)
        overlay = Overlay(overlay_text)
        overlay.visible = True
        self.page.overlay.append(overlay)
        self.page.update()

        save_file_path = await self.handle_save_file()
        logging.info(f"Save path: {save_file_path}")

        def remove_overlay():
            self._uploading = False
            overlay.visible = False
            self.page.overlay.remove(overlay)
            self.page.update()

        if not save_file_path:
            remove_overlay()
            return

        if not save_file_path.lower().endswith(".docx"):
            save_file_path = f"{save_file_path}.docx"

        text_cancel = ft.Text("Отмена", text_align=ft.TextAlign.CENTER)
        button_cancel = StyledButton(
            text_cancel,
            expand=False,
            on_click=lambda: self.docx_processing.cancel(),
        )
        text_loading = ft.Text(
            "Документ создается...",
            size=32,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        loading_ui = ft.Stack(
            expand=True,
            controls=[
                ft.Column(
                    expand=True,
                    align=ft.Alignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[text_loading, ft.ProgressRing()],
                ),
                ft.Container(
                    content=button_cancel,
                    alignment=ft.Alignment.BOTTOM_CENTER,
                    padding=ft.Padding.only(bottom=32),
                    expand=True,
                ),
            ],
        )

        overlay.content = loading_ui
        overlay.update()

        tickets_count_type = str(next(iter(self.segmented_button_ticket_num.selected)))
        practical_rnd_type = str(next(iter(self.segmented_btn_practical.selected)))
        theoretical_rnd_type = str(next(iter(self.segmented_btn_theoretical.selected)))
        tickets_count = None

        if self.textfield_ticket_number.value:
            tickets_count = int(self.textfield_ticket_number.value)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self.docx_processing.process_docx(
                    save_to=save_file_path,
                    subject=(self.dropdown_textfield_subject.text or ""),
                    spec=(self.dropdown_textfield_spec.text or ""),
                    cmk=(self.dropdown_textfield_cmk.text or ""),
                    tutor=(self.dropdown_textfield_tutor.text or ""),
                    date=(self.date_row.value),
                    qualify_status=self.checkbox_qualifying.value,
                    tickets_count=tickets_count,
                    tickets_count_type=tickets_count_type,
                    practical_rnd_type=practical_rnd_type,
                    theoretical_rnd_type=theoretical_rnd_type,
                ),
            )
        except DocxProcessingCancel:
            remove_overlay()
            self.page.show_dialog(WarnPopup("Генерация отменена"))
            return
        except DocxProcessingError as error:
            remove_overlay()
            self.page.show_dialog(WarnPopup(str(error)))
            logging.info(f"Ошибка: {error}'")
            return

        self.show_dialog_generation_complete(save_file_path)
        remove_overlay()

    def show_dialog_generation_complete(self, filepath: str) -> None:
        dialog = StyledAlertDialog(
            title=ft.Text("Документ создан", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment(0, 0),
        )
        responsive_row = ft.ResponsiveRow()
        responsive_row.controls = [
            StyledButton(
                content="Открыть файл",
                icon=ft.Icons.OPEN_IN_NEW,
                expand=True,
                on_click=lambda e: open_file(filepath),
            ),
            StyledButton(
                content="Открыть папку",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=lambda e: open_file(str(Path(filepath).parent)),
            ),
            StyledButton(
                content="Закрыть",
                icon=ft.Icons.CLOSE,
                expand=True,
                on_click=self.page.pop_dialog,
            ),
        ]
        dialog.actions = [responsive_row]
        self.page.show_dialog(dialog)

    def get_ui(self) -> ft.Column:
        self.button_clear_fields.on_click = self._textfield_clear

        def get_card_questions() -> ft.Card:
            column = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Text(
                        "Количество билетов",
                        weight=ft.FontWeight.BOLD,
                        size=18,
                    ),
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
                label = "Практические"
                segmented_btn = self.segmented_btn_practical
            else:
                label = "Теоретические"
                segmented_btn = self.segmented_btn_theoretical

            segmented_btn.segments = [
                ft.Segment(
                    value="fallback",
                    icon=ft.Icons.AUTO_AWESOME,
                    label=ft.Text(
                        "Смешанный",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Не случайный, если закончились — случайный",
                    expand=True,
                ),
                ft.Segment(
                    value="always",
                    icon=ft.Icons.SHUFFLE,
                    label=ft.Text(
                        "Случайный",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Случайный порядок",
                    expand=True,
                ),
                ft.Segment(
                    value="none",
                    icon=ft.Icons.CLOSE,
                    label=ft.Text(
                        "Не случайный",
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    ),
                    tooltip="Последовательный порядок",
                    expand=True,
                ),
            ]

            container_segment = ft.Container(padding=12)
            container_segment.content = ft.Column(
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
            return container_segment

        cards_rnd: List[ft.Control] = [
            ft.Text(
                "Порядок вопросов",
                margin=ft.Margin.only(left=6),
                weight=ft.FontWeight.BOLD,
                size=18,
            ),
            ft.Column(
                expand=True,
                col={"xs": 12, "sm": 6},
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Card(
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
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
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                        content=get_segment_rnd(
                            QuestionType.THEORETICAL,
                        ),
                    )
                ],
            ),
        ]

        wrapped_cards_rnd = ft.ResponsiveRow(
            expand=True,
            run_spacing=0,
            spacing=0,
            controls=[
                ft.Card(
                    content=ft.ResponsiveRow(
                        margin=9,
                        spacing=4,
                        run_spacing=4,
                        controls=cards_rnd,
                    )
                ),
            ],
        )

        responsive_row_textfields = ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            controls=[
                ft.Column(
                    col={"sm": 6},
                    controls=[self.dropdown_textfield_cmk, self.date_row],
                ),
                ft.Column(
                    col={"sm": 6},
                    controls=[
                        self.dropdown_textfield_subject,
                        self.dropdown_textfield_spec,
                    ],
                ),
                self.dropdown_textfield_tutor,
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
                    wrapped_cards_rnd,
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
