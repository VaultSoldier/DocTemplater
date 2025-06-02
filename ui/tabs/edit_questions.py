import logging
from typing import Any
import re

import flet as ft

from app_logic.table import get_selected_row_questions
from app_logic.processing.data_operations import (
    SqliteData,
    TextProcessing,
    clean_question_by_regex,
    docx_extract_questions,
)
from app_logic.processing.docx_creation import Processing
from app_logic.types import QuestionType
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
        table_practical: ft.DataTable,
        table_theoretical: ft.DataTable,
        _build_data_rows,
    ) -> None:
        self.page = page
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

        self.table_practical = table_practical
        self.table_theoretical = table_theoretical

    def refresh_table(
        self,
        questions: dict,
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

    def toggle_row(
        self,
        question_id: int,
        selected_rows: dict[int, bool],
        question_type: QuestionType,
    ) -> None:
        selected_rows[question_id] = not selected_rows[question_id]
        questions = self.sqlite.read_questions_dict(question_type)

        if question_type == QuestionType.PRACTICAL:
            table = self.table_practical
        elif question_type == QuestionType.THEORETICAL:
            table = self.table_theoretical

        table.rows = self.build_data_rows(questions, question_type)
        table.update()

    def toggle_all(self, e, question_type: QuestionType):
        questions = self.sqlite.read_questions_dict(question_type)

        if question_type == QuestionType.PRACTICAL:
            selected = self.selected_rows_practical
            table = self.table_practical
        elif question_type == QuestionType.THEORETICAL:
            selected = self.selected_rows_theoretical
            table = self.table_theoretical

        new_state = not any(selected.values())

        for idx in selected:
            selected[idx] = new_state

        table.rows = self.build_data_rows(questions, question_type)
        table.update()

    def on_pick(self, e: ft.FilePickerResultEvent, overlay: ft.Container):
        overlay.visible = False

        def warning():
            self.page.open(
                WarnPopup("Выберите документ (.docx) или текстовый файл (.txt)")
            )

        if not e.files:
            warning()
            return

        filepath = e.files[0].path
        logging.info(filepath)

        if filepath[-5:].lower() == ".docx":
            new_questions = docx_extract_questions(filepath)
        elif filepath[-4:].lower() == ".txt":
            new_questions = self.text_processing.get_dict(filepath)
        else:
            warning()
            return

        if not new_questions:
            self.page.open(WarnPopup("В файле нету вопросов"))
            return

        # TODO: Доработать ПОПАП
        button_practical = StyledButton("Практические")
        button_theoretical = StyledButton("Теоретические")

        button_practical.on_click = (
            lambda e, qtype=QuestionType.PRACTICAL: on_click_save_to(e, qtype)
        )
        button_theoretical.on_click = (
            lambda e, qtype=QuestionType.THEORETICAL: on_click_save_to(e, qtype)
        )

        dialog_content = ft.Row(expand=True)
        dialog_content.controls = [button_practical, button_theoretical]
        dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=9),
            content_padding=ft.padding.all(14),
            action_button_padding=0,
            actions_padding=0,
            title=ft.Text("Тип вопросов"),
            content=ft.Container(content=dialog_content, padding=9),
        )
        self.page.open(dialog)

        def on_click_save_to(e, qtype):
            button_practical.disabled = True
            button_theoretical.disabled = True
            button_practical.update()
            button_theoretical.update()

            self.sqlite.add_list(new_questions, qtype)
            self.refresh_table(self.sqlite.read_questions_dict(qtype), qtype)
            self.page.close(dialog)

    def on_click_open_textfield(self, e):
        textfield = ft.TextField(multiline=True, min_lines=10)
        button_save = StyledButton("Сохранить")
        button_save.on_click = lambda _: submit(segments_qtype.selected)
        button_close = StyledButton("Закрыть")

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

            questions.clear()
            questions.update(self.sqlite.read_questions_dict(QuestionType(qtype)))
            self.refresh_table(questions, QuestionType(qtype), refresh_questions=False)
            logging.info(f"Сохранённые значения: {values}")
            self.page.close(dialog)

        segments_qtype = StyledSegmentedButton(selected={QuestionType.PRACTICAL.value})
        segments_qtype.segments = [
            ft.Segment(
                expand=True,
                value=QuestionType.PRACTICAL.value,
                label=ft.Text("Практические"),
            ),
            ft.Segment(
                expand=True,
                value=QuestionType.THEORETICAL.value,
                label=ft.Text("Теоретические"),
            ),
        ]

        dialog = StyledAlertDialog(
            modal=True,
            actions_padding=ft.padding.only(left=14, right=14, top=12, bottom=14),
            title="Каждый вопрос должен быть на новой строке",
        )
        dialog.content = ft.Container(content=textfield)
        dialog.actions = [
            ft.Column(
                [
                    ft.Row([segments_qtype], expand=True),
                    ft.Row(controls=[button_save, button_close]),
                ]
            ),
        ]

        button_close.on_click = lambda _: self.page.close(dialog)
        self.page.open(dialog)

    def on_click_upload(self, e, file_picker: ft.FilePicker, overlay: ft.Container):
        overlay.visible = True
        overlay.update()

        file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["docx", "txt"],
            dialog_title="Вопросы к промежуточной аттестации",
        )

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
        self.refresh_table(questions, question_type, refresh_questions=False)

    def on_click_button_delete(self, e):
        if not any(self.selected_rows_practical.values()) and not any(
            self.selected_rows_theoretical.values()
        ):
            self.page.open(WarnPopup("Вопрос(ы) не выбран(ы)"))
            logging.info("Вопросы не выбраны")
            return

        if any(self.selected_rows_practical.values()):
            self.delete_question_by_type(QuestionType.PRACTICAL)
            self.selected_rows_practical.update()
        if any(self.selected_rows_theoretical.values()):
            self.delete_question_by_type(QuestionType.THEORETICAL)
            self.selected_rows_theoretical.update()

    def get_edit_questions_table(
        self, question_type: QuestionType
    ) -> tuple[ft.DataTable, dict[int, str]]:
        """
        Возвращает DataTable и вопросы в dict[id, вопрос]
        """
        if question_type == QuestionType.PRACTICAL:
            selected_rows = self.selected_rows_practical
            questions_label = ft.Text("Практические Вопросы")
        elif question_type == QuestionType.THEORETICAL:
            selected_rows = self.selected_rows_theoretical
            questions_label = ft.Text("Теоретические Вопросы")

        questions = self.sqlite.read_questions_dict(question_type)
        new_questions = get_selected_row_questions(questions, selected_rows)
        textfield_storage: dict[int, str] = dict(new_questions)
        items_len = len(new_questions)

        data_table = ft.DataTable(
            border=ft.Border(),
            show_bottom_border=True,
            columns=[
                ft.DataColumn(ft.Text("№"), numeric=True),
                ft.DataColumn(questions_label),
            ],
        )
        data_table.rows = []

        def on_textfield_change(e):
            textfield_storage[e.control.data] = e.control.value

        for cell_index, (question_id, question) in enumerate(new_questions.items()):
            reversed_cell_id = items_len - cell_index

            tf = StyledTextField(
                border=ft.InputBorder.UNDERLINE,
                data=question_id,
                on_change=on_textfield_change,
                value=question,
            )
            data_table.rows.append(
                ft.DataRow(
                    cells=[ft.DataCell(ft.Text(str(reversed_cell_id))), ft.DataCell(tf)]
                )
            )
        return data_table, textfield_storage

    def on_click_button_edit(self, e):
        tables_data = {}
        table_content = ft.Row()
        button_save = StyledButton(text="Сохранить")
        button_close = StyledButton(text="Закрыть")

        if self.page.width:
            width = self.page.width * 0.50
        else:
            width = 0

        alert_dialog_content = ft.Column(
            width=width,
            spacing=0,
            expand=True,
            controls=[ft.Container(expand=True, content=table_content)],
        )
        alert_dialog = StyledAlertDialog(
            modal=True,
            content=alert_dialog_content,
            actions=[ft.Row([button_save, button_close])],
        )

        # INFO: МОЖНО ОПТИМИЗИРОВАТЬ
        def on_click_button_save(tables_questions: dict, popup, e):
            if QuestionType.PRACTICAL in tables_questions:
                qtype = QuestionType.PRACTICAL
                self.sqlite.edit_questions(tables_questions[qtype])
                self.refresh_table(self.questions_theoretical, qtype)

            if QuestionType.THEORETICAL in tables_questions:
                qtype = QuestionType.THEORETICAL
                self.sqlite.edit_questions(tables_questions[qtype])
                self.refresh_table(self.questions_practical, qtype)
            self.page.close(popup)

        if not any(self.selected_rows_practical.values()) and not any(
            self.selected_rows_theoretical.values()
        ):
            logging.info("Вопрос(ы) не выбран(ы)")
            self.page.open(WarnPopup("Вопрос(ы) не выбран(ы)"))
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
            alert_dialog_content.width = width * 1.4
        elif any(self.selected_rows_practical.values()):
            fillout_qestions(QuestionType.PRACTICAL)
        elif self.selected_rows_theoretical.values():
            fillout_qestions(QuestionType.THEORETICAL)

        button_save.on_click = lambda e: on_click_button_save(
            tables_data, alert_dialog, e
        )
        button_close.on_click = lambda _: self.page.close(alert_dialog)
        self.page.open(alert_dialog)

    def on_click_button_add(self, e):
        textfields = []
        list_view = ft.ListView(padding=0, spacing=9, expand=True)

        def add_textfield(e):
            textfield = StyledTextField(value="", expand=True)
            button_remove = ft.IconButton(
                icon=ft.Icons.CLOSE,
                on_click=lambda _, tf=textfield: remove_textfield(tf),
            )
            textfield.suffix_icon = button_remove
            row = ft.Row(expand=True, controls=[textfield])

            textfields.append((textfield, row))
            list_view.controls.append(row)
            self.page.update()

        add_textfield(None)

        def remove_textfield(tf):
            if len(textfields) == 1:
                return

            for item in textfields:
                if item[0] == tf:
                    textfields.remove(item)
                    list_view.controls.remove(item[1])
                    break
            self.page.update()

        segments_qtype = StyledSegmentedButton(selected={QuestionType.PRACTICAL.value})
        segments_qtype.segments = [
            ft.Segment(
                expand=True,
                value=QuestionType.PRACTICAL.value,
                label=ft.Text("Практические"),
                # icon=ft.Icon(ft.Icons.CHECK_BOX_OUTLINE_BLANK),
            ),
            ft.Segment(
                expand=True,
                value=QuestionType.THEORETICAL.value,
                label=ft.Text("Теоретические"),
                # icon=ft.Icon(ft.Icons.CHECK_BOX_OUTLINE_BLANK),
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

            self.refresh_table(questions, question_type, refresh_questions=False)
            logging.info(f"Сохранённые значения: {values}")
            self.page.close(alert_layout)

        button_add_row = StyledButton(text="Добавить поле", on_click=add_textfield)
        button_save = StyledButton(text="Сохранить", on_click=on_click_save)
        button_close = StyledButton(text="Закрыть")

        column_selections = ft.Column()
        column_selections.controls = [
            ft.Row(expand=True, controls=[segments_qtype]),
            ft.Row(
                controls=[button_add_row, button_save, button_close],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ]

        alert_layout = StyledAlertDialog(modal=True)
        alert_layout.content = ft.Column(
            expand=True,
            tight=True,
            spacing=9,
            controls=[list_view, column_selections],
        )

        button_close.on_click = lambda _: self.page.close(alert_layout)
        self.page.open(alert_layout)


class TabEditQuestions(EditQuestionsTabController):
    def __init__(self, page: ft.Page, tab_label: ft.Text) -> None:
        self.sqlite = SqliteData()
        self.tab_label = tab_label

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

        self.table_practical = self.get_data_table(QuestionType.PRACTICAL)
        self.table_theoretical = self.get_data_table(QuestionType.THEORETICAL)

        super().__init__(
            page, self.table_practical, self.table_theoretical, self._build_data_rows
        )

        self.button_delete = StyledButton(
            height=38,
            width=160,
            expand=2,
            text="Удалить",
            on_click=self.on_click_button_delete,
        )
        self.button_add = StyledButton(
            height=38,
            width=160,
            expand=2,
            text="Добавить",
            on_click=self.on_click_button_add,
        )
        self.button_edit = StyledButton(
            height=38,
            width=160,
            expand=2,
            text="Изменить",
            on_click=self.on_click_button_edit,
        )

        self.button_paste = StyledButton(
            text="Вставить",
            icon=ft.Icons.PASTE,
            on_click=self.on_click_open_textfield,
        )

        # FILEPICKER elements
        overlay = Overlay()
        filepicker = ft.FilePicker(on_result=lambda e: self.on_pick(e, overlay))
        self.page.overlay.extend([overlay, filepicker])
        self.button_upload_docx = StyledButton(
            text=".DOCX или .TXT",
            icon=ft.Icons.FILE_UPLOAD,
            on_click=lambda e: self.on_click_upload(e, filepicker, overlay),
        )

    def get_data_table(self, question_type: QuestionType) -> ft.DataTable:
        data_table = ft.DataTable(
            expand=True,
            vertical_lines=ft.BorderSide(1, ft.Colors.INVERSE_PRIMARY),
            horizontal_lines=ft.BorderSide(1, "dark"),
            show_checkbox_column=True,
            on_select_all=lambda e: self.toggle_all(e, question_type),
            columns=[
                ft.DataColumn(ft.Text("№"), numeric=True),
            ],
            rows=self._build_data_rows(
                questions_dict=self.sqlite.read_questions_dict(question_type),
                question_type=question_type,
            ),
        )

        if question_type == QuestionType.PRACTICAL:
            data_table.columns.append(ft.DataColumn(ft.Text("Практические Вопросы")))
        if question_type == QuestionType.THEORETICAL:
            data_table.columns.append(ft.DataColumn(ft.Text("Теоретические Вопросы")))
        return data_table

    def _build_data_rows(
        self, questions_dict: dict[int, Any], question_type: QuestionType
    ) -> list[ft.DataRow]:
        items = questions_dict.items()
        items_len = len(items)
        rows: list[ft.DataRow] = []

        for cell_index, (question_id, question) in enumerate(items):
            reversed_cell_id = items_len - cell_index
            cell_question = ft.Text(value=str(question), tooltip=str(question))

            row_cells = [
                ft.DataCell(ft.Text(str(reversed_cell_id))),
                ft.DataCell(cell_question),
            ]
            row = ft.DataRow(row_cells, data=question_id)

            if question_type == QuestionType.PRACTICAL:
                row.on_select_changed = lambda e, rid=question_id: self.toggle_row(
                    rid, self.selected_rows_practical, question_type
                )
                row.selected = self.selected_rows_practical.get(question_id)
            elif question_type == QuestionType.THEORETICAL:
                row.on_select_changed = lambda e, rid=question_id: self.toggle_row(
                    rid, self.selected_rows_theoretical, question_type
                )
                row.selected = self.selected_rows_theoretical.get(question_id)
            rows.append(row)
        return rows

    def get_tab_ui(self):
        datatables = ft.Row(
            expand=True,
            controls=[
                ft.ListView(expand=True, controls=[self.table_practical]),
                ft.ListView(expand=True, controls=[self.table_theoretical]),
            ],
        )
        buttons = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        buttons.controls = [
            self.button_add,
            self.button_edit,
            self.button_delete,
            self.button_paste,
            self.button_upload_docx,
        ]

        content = ft.Column(expand=True, spacing=0)
        content.controls = [
            datatables,
            ft.Container(
                margin=ft.margin.only(9, 9, 9, 9),
                content=buttons,
            ),
        ]

        tab_content = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        tab_content.controls = [
            ft.Icon(ft.Icons.EDIT_NOTE, tooltip=self.tab_label.value),
            self.tab_label,
        ]
        return ft.Tab(tab_content=tab_content, content=content)
