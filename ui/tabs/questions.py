import logging
from typing import Any, List, Optional

import flet as ft
import flet_datatable2 as fdt

from core.processing.data import (
    SqliteData,
    TextProcessing,
    clean_question_by_regex,
    docx_extract_questions,
)
from core.processing.docx import Processing
from core.table import get_selected_row_questions
from core.types import AppEvent, QuestionType
from ui.templates import (
    Overlay,
    StyledAlertDialog,
    StyledButton,
    StyledSegmentedButton,
    StyledTextField,
    WarnPopup,
)


class EditQuestionsTabController:
    def __init__(
        self,
        page: ft.Page,
        table_practical: fdt.DataTable2,
        table_theoretical: fdt.DataTable2,
        _build_data_rows,
    ) -> None:
        self.page = page
        self.page.pubsub.subscribe(self.on_pubsub)
        self._uploading = False
        self.build_data_rows = _build_data_rows
        self.doc_processing = Processing()
        self.text_processing = TextProcessing()
        self.sqlite = SqliteData()

        self.questions_practical = self.sqlite.read_questions_dict(
            QuestionType.PRACTICAL
        )
        self.questions_theoretical = self.sqlite.read_questions_dict(
            QuestionType.THEORETICAL
        )

        self.selected_rows_practical = {
            idx: False for idx in self.questions_practical.keys()
        }
        self.selected_rows_theoretical = {
            idx: False for idx in self.questions_theoretical.keys()
        }

        self.dialog_content_edit_questions = ft.Column(expand=True, spacing=0)
        self.table_practical = table_practical
        self.table_theoretical = table_theoretical

    # INFO: reset tables on db reset
    def on_pubsub(self, topic):
        match topic:
            case AppEvent.DB_RESET:
                self.refresh_table(QuestionType.PRACTICAL, refresh_questions=True)
                self.refresh_table(QuestionType.THEORETICAL, refresh_questions=True)

    def refresh_table(
        self,
        question_type: QuestionType,
        refresh_questions: bool = True,
    ):
        if question_type == QuestionType.PRACTICAL:
            selected_rows = self.selected_rows_practical
            questions = self.questions_practical
            table = self.table_practical
        elif question_type == QuestionType.THEORETICAL:
            selected_rows = self.selected_rows_theoretical
            questions = self.questions_theoretical
            table = self.table_theoretical

        if refresh_questions:
            questions.clear()
            questions.update(self.sqlite.read_questions_dict(question_type))

        selected_rows.clear()
        selected_rows.update({idx: False for idx in questions.keys()})
        table.rows = self.build_data_rows(questions, question_type)

        table.update()
        logging.info("Questions table refreshed")

    def toggle_rows(
        self,
        e,
        question_type: QuestionType,
        question_id: Optional[int] = None,
    ) -> None:
        """Toggles one row by id or ALL rows if no id is provided"""
        questions = self.sqlite.read_questions_dict(question_type)

        table_map = {
            QuestionType.PRACTICAL: (
                self.selected_rows_practical,
                self.table_practical,
            ),
            QuestionType.THEORETICAL: (
                self.selected_rows_theoretical,
                self.table_theoretical,
            ),
        }

        try:
            selected, table = table_map[question_type]
        except KeyError:
            raise ValueError(f"Unsupported question type: {question_type}")

        if question_id is not None:
            if question_id not in selected:
                raise ValueError(f"Unkown question_id: {question_id}")
            selected[question_id] = not selected[question_id]
        else:
            new_state = not any(selected.values())
            for idx in selected:
                selected[idx] = new_state

        table.rows = self.build_data_rows(questions, question_type)
        table.update()

    def on_click_paste(self, e):
        button_save = StyledButton(
            tooltip="Сохранить",
            icon=ft.Icons.SAVE,
            content=ft.Text(
                value="Сохранить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            on_click=lambda _: submit(segments_questions_type.selected),
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
        textfield = ft.TextField(
            multiline=True,
            autofocus=True,
            min_lines=10,
            hint_text="Один вопрос — Одна строка. Вопросы разделяются через Enter.",
        )

        # INFO: CAN BE OPTIMISED
        def submit(question_type):
            if not question_type or not textfield.value:
                return

            REGEX = r"^\s*\d+[.)]{1,2}\s*"  # пример: 1) или 1. или 1.)
            qtype = next(iter(question_type))
            questions_raw = textfield.value

            if qtype == QuestionType.PRACTICAL.value:
                questions = self.questions_practical
            elif qtype == QuestionType.THEORETICAL.value:
                questions = self.questions_theoretical
            else:
                return

            button_save.disabled = True
            button_save.update()

            values = [
                cleaned
                for q in questions_raw.splitlines()
                if (cleaned := clean_question_by_regex(REGEX, q)) != ""
            ]

            if not any(values):
                button_save.disabled = False
                button_save.update()
                return

            self.sqlite.add_list(values, QuestionType(qtype))
            logging.info(f"Сохранённые значения: {values}")

            questions.clear()
            questions.update(self.sqlite.read_questions_dict(QuestionType(qtype)))
            self.refresh_table(QuestionType(qtype), refresh_questions=False)
            self.page.pop_dialog()
            self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

        segments_questions_type = StyledSegmentedButton(
            selected=[QuestionType.PRACTICAL.value],
            segments=[
                ft.Segment(
                    label=ft.Text("Практические"),
                    value=QuestionType.PRACTICAL.value,
                    expand=True,
                ),
                ft.Segment(
                    label=ft.Text("Теоретические"),
                    value=QuestionType.THEORETICAL.value,
                    expand=True,
                ),
            ],
        )

        actions: List[ft.Control] = [
            ft.Row([segments_questions_type], expand=True),
            ft.Row([button_save, button_close]),
        ]
        dialog = StyledAlertDialog(
            modal=True,
            actions_padding=ft.Padding.only(left=14, right=14, top=12, bottom=14),
        )
        dialog.content = ft.Container(textfield)
        dialog.actions = [ft.Column(actions)]

        self.page.show_dialog(dialog)

    async def handle_pick_file(self) -> List[ft.FilePickerFile] | None:
        return await ft.FilePicker().pick_files(
            dialog_title="Вопросы к промежуточной аттестации",
            allowed_extensions=["docx", "txt"],
            allow_multiple=False,
        )

    async def on_click_button_upload(self, e: ft.Event[ft.Button]) -> None:
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

        overlay = Overlay(text_value="Выберите файл...", text_color=text_color)
        overlay.visible = True
        self.page.overlay.append(overlay)
        self.page.update()
        self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

        try:
            picked_files = await self.handle_pick_file()
        finally:
            self._uploading = False
            overlay.visible = False
            overlay.update()
            self.page.overlay.remove(overlay)
            self.page.update()

        def warning():
            self.page.show_dialog(
                WarnPopup("Выберите документ (.docx) или текстовый файл (.txt)")
            )

        if not picked_files:
            warning()
            return

        filepath = picked_files[0].path
        logging.info(filepath)

        if not filepath:
            warning()
            return

        if filepath[-5:].lower() == ".docx":
            new_questions = docx_extract_questions(filepath)
        elif filepath[-4:].lower() == ".txt":
            new_questions = self.text_processing.get_dict(filepath)
        else:
            warning()
            return

        if not new_questions:
            self.page.show_dialog(WarnPopup("В файле нету вопросов"))
            return

        button_practical = StyledButton("Практические")
        button_theoretical = StyledButton("Теоретические")

        button_practical.on_click = lambda e, qtype=QuestionType.PRACTICAL: (
            on_click_save_to(e, qtype)
        )
        button_theoretical.on_click = lambda e, qtype=QuestionType.THEORETICAL: (
            on_click_save_to(e, qtype)
        )

        dialog_content = ft.Row(
            expand=True,
            controls=[button_practical, button_theoretical],
        )
        # FIX: сделать распределение вопросов
        dialog = ft.AlertDialog(
            title=ft.Text("Тип вопросов", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment(0, 0),
            action_button_padding=0,
            actions_padding=0,
            content_padding=ft.Padding.all(9),
            shape=ft.RoundedRectangleBorder(radius=9),
            content=ft.Container(content=dialog_content, padding=9),
            modal=True,
        )
        self.page.show_dialog(dialog)

        def on_click_save_to(e, qtype):
            button_practical.disabled = True
            button_theoretical.disabled = True
            button_practical.update()
            button_theoretical.update()

            self.sqlite.add_list(new_questions, qtype)
            self.refresh_table(qtype)
            self.page.pop_dialog()
            self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

    def delete_question_by_type(self, question_type: QuestionType):
        if question_type == QuestionType.PRACTICAL:
            selected_rows_copy = self.selected_rows_practical.copy()
            questions = self.questions_practical
        elif question_type == QuestionType.THEORETICAL:
            selected_rows_copy = self.selected_rows_theoretical.copy()
            questions = self.questions_theoretical

        for idx, bool in selected_rows_copy.items():
            if not bool:
                continue

            questions.pop(idx)
            self.sqlite.remove_by_id(idx)

        selected_rows_copy.clear()
        self.refresh_table(question_type, refresh_questions=False)

    def on_click_button_delete(self, e):
        if not any(self.selected_rows_practical.values()) and not any(
            self.selected_rows_theoretical.values()
        ):
            self.page.show_dialog(WarnPopup("Вопрос(ы) не выбран(ы)"))
            logging.info("Вопросы не выбраны")
            return

        if any(self.selected_rows_practical.values()):
            self.delete_question_by_type(QuestionType.PRACTICAL)
            self.selected_rows_practical.update
        if any(self.selected_rows_theoretical.values()):
            self.delete_question_by_type(QuestionType.THEORETICAL)
            self.selected_rows_theoretical.update
        self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

    def get_edit_questions_table(
        self, question_type: QuestionType
    ) -> tuple[fdt.DataTable2, dict[int, str]]:
        """
        Возвращает DataTable и вопросы в dict[id, вопрос]
        """
        if question_type == QuestionType.PRACTICAL:
            selected_rows = self.selected_rows_practical
            questions_label = ft.Text(
                "Практические",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            )

        elif question_type == QuestionType.THEORETICAL:
            selected_rows = self.selected_rows_theoretical
            questions_label = ft.Text(
                "Теоретические",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            )

        questions = self.sqlite.read_questions_dict(question_type)
        new_questions = get_selected_row_questions(questions, selected_rows)
        textfield_storage: dict[int, str] = dict(new_questions)

        data_table = fdt.DataTable2(
            show_bottom_border=True,
            heading_row_color=ft.Colors.SURFACE_CONTAINER,
            sort_column_index=0,
            column_spacing=26,
            horizontal_margin=12,
            heading_row_height=40,
            data_row_height=38,
            columns=[
                fdt.DataColumn2(
                    fixed_width=32,
                    heading_row_alignment=ft.MainAxisAlignment.START,
                    label=ft.Text(
                        value="№", overflow=ft.TextOverflow.FADE, no_wrap=True
                    ),
                    numeric=True,
                ),
                fdt.DataColumn2(label=questions_label),
            ],
        )

        def on_textfield_change(e):
            textfield_storage[e.control.data] = e.control.value

        for cell_index, (question_id, question) in enumerate(new_questions.items()):
            teftfield = StyledTextField(
                border=ft.InputBorder.UNDERLINE,
                data=question_id,
                on_change=on_textfield_change,
                value=question,
                dense=False,
                height=38,
                content_padding=ft.Padding(0, -9),  # vertical center
            )
            data_table.rows.append(
                fdt.DataRow2(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                value=str(cell_index + 1),
                                overflow=ft.TextOverflow.FADE,
                                no_wrap=True,
                            )
                        ),
                        ft.DataCell(teftfield),
                    ],
                )
            )
        return data_table, textfield_storage

    def on_click_button_edit(self, e):
        tables_data = {}
        table_content = ft.Row(expand=True)
        button_save = StyledButton(
            content=ft.Text(
                value="Сохранить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.SAVE,
        )
        button_close = StyledButton(
            content=ft.Text(
                value="Закрыть",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.CLOSE,
        )

        if self.page.width:
            width = self.page.width * 0.75
        else:
            width = None

        self.dialog_content_edit_questions.controls = [table_content]
        self.dialog_content_edit_questions.width = width

        dialog = StyledAlertDialog(
            modal=True,
            content=self.dialog_content_edit_questions,
            actions=[ft.Row([button_save, button_close])],
        )

        def on_click_button_save(tables_questions: dict, e):
            if QuestionType.PRACTICAL in tables_questions:
                self.sqlite.edit_questions(tables_questions[QuestionType.PRACTICAL])
                self.refresh_table(QuestionType.PRACTICAL)

            if QuestionType.THEORETICAL in tables_questions:
                self.sqlite.edit_questions(tables_questions[QuestionType.THEORETICAL])
                self.refresh_table(QuestionType.THEORETICAL)
            self.page.pop_dialog()

        if not any(self.selected_rows_practical.values()) and not any(
            self.selected_rows_theoretical.values()
        ):
            logging.info("Вопрос(ы) не выбран(ы)")
            self.page.show_dialog(WarnPopup("Вопрос(ы) не выбран(ы)"))
            return

        def fillout_qestions(question_type: QuestionType):
            table, questions = self.get_edit_questions_table(question_type)
            tables_data[question_type] = questions
            table_content.controls.append(ft.ListView(expand=True, controls=[table]))

        if any(self.selected_rows_practical.values()) and any(
            self.selected_rows_theoretical.values()
        ):
            fillout_qestions(QuestionType.PRACTICAL)
            fillout_qestions(QuestionType.THEORETICAL)
        elif any(self.selected_rows_practical.values()):
            fillout_qestions(QuestionType.PRACTICAL)
        elif any(self.selected_rows_theoretical.values()):
            fillout_qestions(QuestionType.THEORETICAL)

        button_save.on_click = lambda e: on_click_button_save(tables_data, e)
        button_close.on_click = self.page.pop_dialog
        self.page.show_dialog(dialog)

    def on_click_button_add(self, e):
        textfields = []
        list_view = ft.ListView(padding=14, spacing=9, expand=True)

        def add_row(e):
            textfield = StyledTextField(
                value="",
                expand=True,
                margin=ft.Margin.only(left=14, right=14),
            )
            button_remove = ft.IconButton(
                icon=ft.Icons.CLOSE,
                on_click=lambda _, tf=textfield: remove_textfield(tf),
            )
            textfield.suffix_icon = button_remove
            row = ft.Row(expand=True, controls=[textfield])

            textfields.append([textfield, row])
            list_view.controls.append(row)
            self.page.update()

        add_row(None)

        def remove_textfield(tf):
            if len(textfields) == 1:
                return

            for item in textfields:
                if item[0] == tf:
                    textfields.remove(item)
                    list_view.controls.remove(item[1])
                    break
            self.page.update()

        segments_qtype = StyledSegmentedButton(selected=[QuestionType.PRACTICAL.value])
        segments_qtype.segments = [
            ft.Segment(
                expand=True,
                value=QuestionType.PRACTICAL.value,
                label=ft.Text(
                    value="Практические",
                    overflow=ft.TextOverflow.FADE,
                    no_wrap=True,
                ),
            ),
            ft.Segment(
                expand=True,
                value=QuestionType.THEORETICAL.value,
                label=ft.Text(
                    value="Теоретические",
                    overflow=ft.TextOverflow.FADE,
                    no_wrap=True,
                ),
            ),
        ]

        # INFO: МОЖНО ОПТИМИЗИРОВАТЬ СОХРАНЕНИЕ ДАННЫХ
        def on_click_save(e):
            values = [
                textfield_data.value.strip()
                for textfield_data, _ in textfields
                if textfield_data.value.strip()
            ]
            if not values or not segments_qtype.selected:
                return

            qtype = next(iter(segments_qtype.selected))

            if qtype == QuestionType.PRACTICAL.value:
                question_type = QuestionType.PRACTICAL
                questions = self.questions_practical
            elif qtype == QuestionType.THEORETICAL.value:
                question_type = QuestionType.THEORETICAL
                questions = self.questions_theoretical
            else:
                return

            self.sqlite.add_list(values, question_type)
            questions.clear()
            questions.update(self.sqlite.read_questions_dict(question_type))

            self.refresh_table(question_type, refresh_questions=False)
            logging.info(f"Сохранённые значения: {values}")
            self.page.pop_dialog()
            self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

        button_add_row = StyledButton(
            content=ft.Text(
                value="Добавить",
                tooltip="Добавить поле",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.ADD,
            on_click=add_row,
        )
        button_save = StyledButton(
            content=ft.Text(
                value="Сохранить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.SAVE,
            on_click=on_click_save,
        )
        button_close = StyledButton(
            content=ft.Text(
                value="Закрыть",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.CLOSE,
        )

        column_selections = ft.Column()
        column_selections.controls = [
            ft.Row(expand=True, controls=[segments_qtype]),
            ft.Row(
                controls=[button_add_row, button_save, button_close],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ]

        alert_layout = StyledAlertDialog(
            content_padding=ft.Padding.all(0),
            modal=True,
        )
        alert_layout.content = ft.Stack(
            controls=[
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    margin=ft.Margin.only(top=14, bottom=12, left=14, right=14),
                    expand=True,
                ),
                ft.Column(
                    expand=True,
                    tight=True,
                    spacing=9,
                    controls=[
                        ft.Container(
                            list_view,
                            margin=ft.Margin.only(top=14, bottom=12),
                            expand=True,
                        )
                    ],
                ),
            ]
        )
        alert_layout.actions = [column_selections]

        button_close.on_click = self.page.pop_dialog
        self.page.show_dialog(alert_layout)


class TabEditQuestions(EditQuestionsTabController):
    def __init__(self, page: ft.Page) -> None:
        sqlite = SqliteData()

        questions_practical = sqlite.read_questions_dict(QuestionType.PRACTICAL)
        questions_theoretical = sqlite.read_questions_dict(QuestionType.THEORETICAL)

        # Must exist before _make_table → _build_data_rows accesses them
        self.selected_rows_practical = {idx: False for idx in questions_practical}
        self.selected_rows_theoretical = {idx: False for idx in questions_theoretical}

        table_practical = self._make_table(QuestionType.PRACTICAL, questions_practical)
        table_theoretical = self._make_table(
            QuestionType.THEORETICAL, questions_theoretical
        )

        super().__init__(
            page, table_practical, table_theoretical, self._build_data_rows
        )

        self.button_delete = StyledButton(
            content=ft.Text(
                value="Удалить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.DELETE,
            height=38,
            width=160,
            expand=2,
            on_click=self.on_click_button_delete,
        )
        self.button_add = StyledButton(
            content=ft.Text(
                value="Добавить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.ADD,
            width=160,
            height=38,
            expand=2,
            on_click=self.on_click_button_add,
        )
        self.button_edit = StyledButton(
            content=ft.Text(
                value="Изменить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            icon=ft.Icons.EDIT,
            width=160,
            height=38,
            expand=2,
            on_click=self.on_click_button_edit,
        )

        self.button_paste = StyledButton(
            content=ft.Text(
                value="Вставить",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            tooltip="Вставить",
            icon=ft.Icons.PASTE,
            on_click=self.on_click_paste,
        )

        self.button_upload_docx = StyledButton(
            content=ft.Text(
                value="Импорт",
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            ),
            tooltip="Импорт",
            icon=ft.Icons.FILE_UPLOAD,
            on_click=self.on_click_button_upload,
        )

    def _make_table(
        self, question_type: QuestionType, questions: dict
    ) -> fdt.DataTable2:
        if question_type == QuestionType.PRACTICAL:
            label = ft.Text("Практические", overflow=ft.TextOverflow.FADE, no_wrap=True)
        elif question_type == QuestionType.THEORETICAL:
            label = ft.Text(
                "Теоретические", overflow=ft.TextOverflow.FADE, no_wrap=True
            )

        return fdt.DataTable2(
            show_checkbox_column=True,
            on_select_all=lambda e: self.toggle_rows(e, question_type),
            heading_row_color=ft.Colors.SURFACE_CONTAINER,
            sort_column_index=0,
            column_spacing=26,
            horizontal_margin=12,
            heading_row_height=40,
            data_row_height=38,
            expand=True,
            columns=[
                fdt.DataColumn2(
                    fixed_width=32,
                    heading_row_alignment=ft.MainAxisAlignment.START,
                    label=ft.Text("№", overflow=ft.TextOverflow.FADE, no_wrap=True),
                    numeric=True,
                ),
                fdt.DataColumn2(label=label),
            ],
            rows=self._build_data_rows(
                questions_dict=questions,
                question_type=question_type,
            ),
        )

    def _build_data_rows(
        self, questions_dict: dict[int, Any], question_type: QuestionType
    ) -> list[ft.DataRow | fdt.DataRow2]:
        items = questions_dict.items()
        rows: list[ft.DataRow] = []

        for index, (question_id, question) in enumerate(items):
            cell_index_text = str(index + 1)
            cell_index = ft.Text(
                value=cell_index_text,
                tooltip=cell_index_text,
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            )
            cell_question = ft.Text(
                value=str(question),
                tooltip=str(question),
                overflow=ft.TextOverflow.FADE,
                no_wrap=True,
            )

            row = fdt.DataRow2(
                cells=[
                    ft.DataCell(cell_index),
                    ft.DataCell(cell_question),
                ],
                data=question_id,
            )

            row.on_select_change = lambda e, rid=question_id: self.toggle_rows(
                e,
                question_type=question_type,
                question_id=rid,
            )

            if question_type == QuestionType.PRACTICAL:
                selected_dict = self.selected_rows_practical
            elif question_type == QuestionType.THEORETICAL:
                selected_dict = self.selected_rows_theoretical

            row.selected = selected_dict.get(question_id, False)
            rows.append(row)
        return rows

    def get_ui(self):
        datatables = ft.Row(
            spacing=9,
            expand=True,
            controls=[
                ft.ListView(expand=True, controls=[self.table_practical]),
                ft.ListView(expand=True, controls=[self.table_theoretical]),
            ],
        )
        buttons = ft.Row(
            margin=ft.Margin.all(9),
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                self.button_add,
                self.button_edit,
                self.button_delete,
                self.button_paste,
                self.button_upload_docx,
            ],
        )
        tab = ft.Column([datatables, buttons])
        return tab
