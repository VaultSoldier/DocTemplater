import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any, List

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
    OverlayText,
    StyledAlertDialog,
    StyledButton,
    StyledSegmentedButton,
    StyledTextField,
    WarnPopup,
)


@dataclass
class _TableState:
    questions: dict[int, Any]
    selected: dict[int, bool]
    lock: threading.Lock = threading.Lock.__new__(threading.Lock)

    def __post_init__(self) -> None:
        self.lock = threading.Lock()


def _make_table(
    state: "_TableState",
    label: str | ft.Control,
    question_type: QuestionType,
    sqlite: SqliteData,
) -> fdt.DataTable2:
    table = fdt.DataTable2(
        show_checkbox_column=True,
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
    )
    table.on_select_all = lambda e: _toggle_rows(
        e,
        state=state,
        table=table,
        sqlite=sqlite,
        question_type=question_type,
        question_id=None,
    )
    table.rows = _build_data_rows(
        state=state,
        question_type=question_type,
        table=table,
        sqlite=sqlite,
    )
    return table


def _build_data_rows(
    state: "_TableState",
    question_type: QuestionType,
    table: fdt.DataTable2,
    sqlite: SqliteData,
) -> list[ft.DataRow]:
    rows: list[ft.DataRow] = []

    for index, (question_id, question) in enumerate(list(state.questions.items())):
        row = fdt.DataRow2(
            cells=[
                ft.DataCell(
                    ft.Text(
                        value=str(index + 1),
                        tooltip=str(index + 1),
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    )
                ),
                ft.DataCell(
                    ft.Text(
                        value=str(question),
                        tooltip=str(question),
                        overflow=ft.TextOverflow.FADE,
                        no_wrap=True,
                    )
                ),
            ],
            data=question_id,
            selected=state.selected.get(question_id, False),
        )
        row.on_select_change = lambda e, rid=question_id: _toggle_rows(
            e,
            state=state,
            table=table,
            sqlite=sqlite,
            question_type=question_type,
            question_id=rid,
        )
        rows.append(row)

    return rows


def _toggle_rows(
    e,
    state: "_TableState",
    table: fdt.DataTable2,
    sqlite: SqliteData,
    question_type: QuestionType,
    question_id: int | None = None,
) -> None:
    """Toggle one row by id, or ALL rows when question_id is None."""
    if not state.lock.acquire(blocking=False):
        return  # re-entrant call from flet_datatable2 during row rebuild — skip

    try:
        if question_id is not None:
            if question_id not in state.selected:
                raise ValueError(f"Unknown question_id: {question_id}")
            state.selected[question_id] = not state.selected[question_id]
        else:
            new_state = str(e.data).lower() == "true"
            for idx in state.selected:
                state.selected[idx] = new_state

        table.rows = _build_data_rows(
            state=state,
            question_type=question_type,
            table=table,
            sqlite=sqlite,
        )
        table.update()
    finally:
        state.lock.release()


class EditQuestionsTabController:
    def __init__(
        self,
        page: ft.Page,
        table_practical: fdt.DataTable2 | None,
        table_theoretical: fdt.DataTable2 | None,
    ) -> None:
        self.page = page
        self.page.pubsub.subscribe(self.on_pubsub)
        self._warn_task = None
        self._uploading = False
        self._next_id = 0
        self.doc_processing = Processing()
        self.text_processing = TextProcessing()
        self.sqlite = SqliteData()

        questions_practical = self.sqlite.read_questions_dict(QuestionType.PRACTICAL)
        questions_theoretical = self.sqlite.read_questions_dict(
            QuestionType.THEORETICAL
        )

        self._state_practical = _TableState(
            questions=questions_practical,
            selected={idx: False for idx in questions_practical},
        )
        self._state_theoretical = _TableState(
            questions=questions_theoretical,
            selected={idx: False for idx in questions_theoretical},
        )

        self.dialog_content_tables = ft.Row(expand=True, spacing=4)
        self.dialog_content_edit_questions = ft.Column(expand=True, spacing=0)
        self.table_practical: fdt.DataTable2 | None = table_practical
        self.table_theoretical: fdt.DataTable2 | None = table_theoretical

    def _get_type_state(
        self, question_type: QuestionType
    ) -> tuple["_TableState", fdt.DataTable2 | None]:
        """Return the (_TableState, table) pair for a given QuestionType."""
        match question_type:
            case QuestionType.PRACTICAL:
                return self._state_practical, self.table_practical
            case QuestionType.THEORETICAL:
                return self._state_theoretical, self.table_theoretical
            case _:
                raise ValueError(f"Unknown QuestionType: {question_type}")

    def on_pubsub(self, topic: AppEvent) -> None:
        match topic:
            case AppEvent.DB_RESET:
                self.refresh_table(QuestionType.PRACTICAL, refresh_questions=True)
                self.refresh_table(QuestionType.THEORETICAL, refresh_questions=True)

    def refresh_table(
        self,
        question_type: QuestionType,
        refresh_questions: bool = True,
    ) -> None:
        state, table = self._get_type_state(question_type)

        if table is None:
            return

        if refresh_questions:
            state.questions.clear()
            state.questions.update(self.sqlite.read_questions_dict(question_type))

        state.selected.clear()
        state.selected.update({idx: False for idx in state.questions})

        table.rows = _build_data_rows(
            state=state,
            question_type=question_type,
            table=table,
            sqlite=self.sqlite,
        )
        table.update()
        logging.info(f"{question_type.name} table refreshed")

    def on_click_paste(self, e) -> None:
        textfield = ft.TextField(
            multiline=True,
            autofocus=True,
            min_lines=10,
            hint_text="Один вопрос — Одна строка. Вопросы разделяются через Enter.",
        )
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

        def submit() -> None:
            if not segments_questions_type.selected or not textfield.value:
                return

            REGEX = r"^\s*\d+[.)]{1,2}\s*"
            qtype = next(iter(segments_questions_type.selected))
            questions_raw = textfield.value

            try:
                question_type = QuestionType(qtype)
            except ValueError:
                return

            button_save.disabled = True
            button_save.update()

            values = [
                cleaned
                for q in questions_raw.splitlines()
                if (cleaned := clean_question_by_regex(REGEX, q)) != ""
            ][::-1]  # reverse list

            if not values:
                button_save.disabled = False
                button_save.update()
                return

            state, _ = self._get_type_state(question_type)
            self.sqlite.add_list(values, question_type)
            logging.info(f"Сохранённые значения: {values}")

            state.questions.clear()
            state.questions.update(self.sqlite.read_questions_dict(question_type))
            self.refresh_table(question_type, refresh_questions=False)
            self.page.pop_dialog()
            self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

        button_save = StyledButton(
            tooltip="Сохранить",
            icon=ft.Icons.SAVE,
            content=ft.Text(
                value="Сохранить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            on_click=submit,
        )
        button_close = StyledButton(
            tooltip="Закрыть",
            icon=ft.Icons.CLOSE,
            content=ft.Text(
                value="Закрыть", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            on_click=self.page.pop_dialog,
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

        color = ft.Colors.WHITE
        if self.page.theme_mode == ft.ThemeMode.LIGHT or (
            self.page.theme_mode == ft.ThemeMode.SYSTEM
            and self.page.platform_brightness == ft.Brightness.LIGHT
        ):
            color = ft.Colors.GREY_800

        overlay = Overlay(OverlayText("Выберите файл...", color=color))
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

        error_message = "Выберите документ (.docx) или текстовый файл (.txt)"

        if not picked_files:
            self.page.show_dialog(WarnPopup(error_message))
            return

        filepath = picked_files[0].path
        logging.info(filepath)

        if not filepath:
            self.page.show_dialog(WarnPopup(error_message))
            return

        if filepath.lower().endswith(".docx"):
            new_questions = docx_extract_questions(filepath)
        elif filepath.lower().endswith(".txt"):
            new_questions = self.text_processing.get_dict(filepath)
        else:
            self.page.show_dialog(WarnPopup(error_message))
            return

        if not new_questions:
            self.page.show_dialog(WarnPopup("Не удалось найти данные"))
            return

        def next_id() -> int:
            self._next_id += 1
            return self._next_id

        all_questions: dict[int, str] = {next_id(): q for q in new_questions}
        practical_questions: dict[int, str] = {}
        theoretical_questions: dict[int, str] = {}

        all_selected: dict[int, bool] = {k: False for k in all_questions}
        practical_selected: dict[int, bool] = {}
        theoretical_selected: dict[int, bool] = {}

        _rebuilding = [False]

        def _make_upload_table(label: str) -> fdt.DataTable2:
            return fdt.DataTable2(
                show_checkbox_column=True,
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
                    fdt.DataColumn2(
                        label=ft.Text(
                            label, overflow=ft.TextOverflow.FADE, no_wrap=True
                        )
                    ),
                ],
            )

        def _build_upload_rows(
            questions: dict[int, str],
            selected: dict[int, bool],
            table: fdt.DataTable2,
        ) -> list[ft.DataRow]:
            rows: list[ft.DataRow] = []
            for display_idx, (qid, text) in enumerate(list(questions.items())):
                textfield = StyledTextField(
                    border=ft.InputBorder.UNDERLINE,
                    data=qid,
                    value=text,
                    dense=False,
                    height=38,
                    content_padding=ft.Padding(0, -9),
                    on_change=lambda ev, q=questions: q.update(
                        {ev.control.data: ev.control.value}
                    ),
                )
                row = fdt.DataRow2(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                value=str(display_idx + 1),
                                overflow=ft.TextOverflow.FADE,
                                no_wrap=True,
                            )
                        ),
                        ft.DataCell(textfield),
                    ],
                    data=qid,
                    selected=selected.get(qid, False),
                )
                row.on_select_change = (
                    lambda ev, rid=qid, sel=selected, t=table, q=questions: (
                        _toggle_upload_row(rid, sel, t, q)
                    )
                )
                rows.append(row)
            return rows

        def _refresh(
            questions: dict[int, str],
            selected: dict[int, bool],
            table: fdt.DataTable2,
        ) -> None:
            table.rows = _build_upload_rows(questions, selected, table)
            table.update()

        def _toggle_upload_row(
            qid: int,
            selected: dict[int, bool],
            table: fdt.DataTable2,
            questions: dict[int, str],
        ) -> None:
            if _rebuilding[0]:
                return
            _rebuilding[0] = True
            try:
                selected[qid] = not selected[qid]
                _refresh(questions, selected, table)
            finally:
                _rebuilding[0] = False

        def _toggle_all_upload(
            ev,
            selected: dict[int, bool],
            questions: dict[int, str],
            table: fdt.DataTable2,
        ) -> None:
            if _rebuilding[0]:
                return
            _rebuilding[0] = True
            try:
                new_state = str(ev.data).lower() == "true"
                for keys in selected:
                    selected[keys] = new_state
                _refresh(questions, selected, table)
            finally:
                _rebuilding[0] = False

        table_all = _make_upload_table("Вопросы")
        table_practical = _make_upload_table("Практические")
        table_theoretical = _make_upload_table("Теоретические")

        table_all.on_select_all = lambda ev: _toggle_all_upload(
            ev, all_selected, all_questions, table_all
        )
        table_practical.on_select_all = lambda ev: _toggle_all_upload(
            ev, practical_selected, practical_questions, table_practical
        )
        table_theoretical.on_select_all = lambda ev: _toggle_all_upload(
            ev, theoretical_selected, theoretical_questions, table_theoretical
        )

        table_all.rows = _build_upload_rows(all_questions, all_selected, table_all)

        def _move(
            target_questions: dict[int, str],
            target_selected: dict[int, bool],
            target_table: fdt.DataTable2,
        ) -> None:
            changed = False
            for src_question, src_selected, src_table in [
                (all_questions, all_selected, table_all),
                (practical_questions, practical_selected, table_practical),
                (theoretical_questions, theoretical_selected, table_theoretical),
            ]:
                if src_question is target_questions:
                    continue

                ids = [keys for keys, values in src_selected.items() if values]
                for id in ids:
                    target_questions[id] = src_question.pop(id)
                    target_selected[id] = False
                    del src_selected[id]

                if ids:
                    _refresh(src_question, src_selected, src_table)
                    changed = True

            if changed:
                _refresh(target_questions, target_selected, target_table)

        warn_text = ft.Text(
            value="",
            color=ft.Colors.ERROR,
            text_align=ft.TextAlign.CENTER,
            visible=False,
            size=18,
        )

        warn_container = ft.Container(warn_text, alignment=ft.Alignment.CENTER)

        def _warn(msg: str) -> None:
            if self._warn_task is not None and not self._warn_task.done():
                self._warn_task.cancel()

            warn_container.margin = ft.Margin.only(bottom=12, top=8)
            warn_text.value = msg
            warn_text.visible = True
            self.page.update()

            async def _hide() -> None:
                await asyncio.sleep(2.6)
                warn_container.margin = ft.Margin.all(0)
                warn_text.value = ""
                warn_text.visible = False
                self.page.update()

            self._warn_task = self.page.run_task(_hide)

        def on_delete_selected(_ev) -> None:
            changed = False
            for selected, question, table in [
                (all_selected, all_questions, table_all),
                (practical_selected, practical_questions, table_practical),
                (theoretical_selected, theoretical_questions, table_theoretical),
            ]:
                ids = [keys for keys, values in selected.items() if values]
                for id in ids:
                    del question[id]
                    del selected[id]
                if ids:
                    _refresh(question, selected, table)
                    changed = True
            if not changed:
                _warn("Вопрос(ы) не выбран(ы)")

        def on_move_to_practical(_ev) -> None:
            _move(practical_questions, practical_selected, table_practical)

        def on_move_to_theoretical(_ev) -> None:
            _move(theoretical_questions, theoretical_selected, table_theoretical)

        def on_save(_ev) -> None:
            if not practical_questions and not theoretical_questions:
                _warn("Нет вопросов для сохранения")
                return

            if practical_questions:
                self.sqlite.add_list(
                    list(practical_questions.values())[::-1], QuestionType.PRACTICAL
                )
                self._state_practical.questions.clear()
                self._state_practical.questions.update(
                    self.sqlite.read_questions_dict(QuestionType.PRACTICAL)
                )
                self.refresh_table(QuestionType.PRACTICAL, refresh_questions=False)

            if theoretical_questions:
                self.sqlite.add_list(
                    list(theoretical_questions.values())[::-1], QuestionType.THEORETICAL
                )
                self._state_theoretical.questions.clear()
                self._state_theoretical.questions.update(
                    self.sqlite.read_questions_dict(QuestionType.THEORETICAL)
                )
                self.refresh_table(QuestionType.THEORETICAL, refresh_questions=False)

            logging.info(
                f"Импорт сохранён: практических={len(practical_questions)}, "
                f"теоретических={len(theoretical_questions)}"
            )
            self.page.pop_dialog()
            self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

        button_to_practical = StyledButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.ARROW_BACK)],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=on_move_to_practical,
        )
        button_to_theoretical = StyledButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.ARROW_FORWARD)],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=on_move_to_theoretical,
        )
        button_delete = StyledButton(
            content=ft.Text("Удалить", overflow=ft.TextOverflow.FADE, no_wrap=True),
            icon=ft.Icons.DELETE,
            on_click=on_delete_selected,
            expand=2,
        )
        button_save = StyledButton(
            content=ft.Text("Сохранить", overflow=ft.TextOverflow.FADE, no_wrap=True),
            icon=ft.Icons.SAVE,
            on_click=on_save,
            expand=2,
        )
        button_cancel = StyledButton(
            content=ft.Text("Отмена", overflow=ft.TextOverflow.FADE, no_wrap=True),
            icon=ft.Icons.CLOSE,
            on_click=self.page.pop_dialog,
            expand=True,
        )

        self.dialog_content_tables.controls = [
            ft.Container(table_practical, expand=True),
            ft.Container(table_all, expand=True),
            ft.Container(table_theoretical, expand=True),
        ]
        self.dialog_content_tables.visible = False

        def on_click_save_to(e, question_type):
            button_practical.disabled = True
            button_theoretical.disabled = True
            button_practical.update()
            button_theoretical.update()

            self.sqlite.add_list(new_questions[::-1], question_type)
            self.refresh_table(question_type, refresh_questions=True)
            self.page.pop_dialog()

        button_practical = StyledButton(
            ft.Text("Практические", overflow=ft.TextOverflow.FADE, no_wrap=True),
            on_click=lambda e, qtype=QuestionType.PRACTICAL: on_click_save_to(e, qtype),
        )
        button_theoretical = StyledButton(
            ft.Text("Теоретические", overflow=ft.TextOverflow.FADE, no_wrap=True),
            on_click=lambda e, qtype=QuestionType.THEORETICAL: on_click_save_to(
                e, qtype
            ),
        )

        def on_click_button_edit(e) -> None:
            dialog.content_padding = ft.Padding.only(
                left=14, right=14, top=14, bottom=0
            )
            dialog.actions_padding = ft.Padding.only(
                left=14, right=14, top=4, bottom=14
            )
            initial_actions.visible = False
            edit_actions.visible = True
            button_cancel.expand = 2
            self.dialog_content_tables.visible = True
            self.page.update()

        button_edit = StyledButton(
            ft.Text("Распределить", overflow=ft.TextOverflow.FADE, no_wrap=True),
            icon=ft.Icons.EDIT,
            on_click=on_click_button_edit,
            expand=True,
        )

        initial_actions = ft.Column(
            controls=[
                ft.Row([button_practical, button_theoretical]),
                ft.Row([button_edit]),
                ft.Row([button_cancel]),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            visible=True,
        )

        edit_actions = ft.Column(
            controls=[
                warn_container,
                ft.Row(
                    controls=[
                        button_to_practical,
                        button_to_theoretical,
                        button_save,
                        button_delete,
                        button_cancel,
                    ],
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            visible=False,
        )

        dialog = StyledAlertDialog(
            actions_padding=ft.Padding.only(left=14, right=14, top=14, bottom=14),
            content=self.dialog_content_tables,
            actions=[initial_actions, edit_actions],
            modal=True,
            expand=True,
        )

        self.page.show_dialog(dialog)

    def delete_question_by_type(self, question_type: QuestionType) -> None:
        state, _ = self._get_type_state(question_type)

        ids_to_delete = [
            idx for idx, is_selected in state.selected.items() if is_selected
        ]
        for idx in ids_to_delete:
            state.questions.pop(idx, None)
            self.sqlite.remove_by_id(idx)

        self.refresh_table(question_type, refresh_questions=False)

    def on_click_button_delete(self, e) -> None:
        has_practical = any(self._state_practical.selected.values())
        has_theoretical = any(self._state_theoretical.selected.values())

        if not has_practical and not has_theoretical:
            self.page.show_dialog(WarnPopup("Вопрос(ы) не выбран(ы)"))
            logging.info("Вопросы не выбраны")
            return

        if has_practical:
            self.delete_question_by_type(QuestionType.PRACTICAL)
        if has_theoretical:
            self.delete_question_by_type(QuestionType.THEORETICAL)

        self.page.pubsub.send_all(AppEvent.TABLE_CHANGED)

    def _make_simple_table(self, label: ft.Control) -> fdt.DataTable2:
        """Headerless table for dialogs that don't need selection."""
        return fdt.DataTable2(
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
                fdt.DataColumn2(label=label),
            ],
        )

    def get_questions_table_and_data(
        self, question_type: QuestionType
    ) -> tuple[ft.DataTable, dict[int, str]]:
        """Returns a DataTable and editable questions as dict[id, question]."""
        state, _ = self._get_type_state(question_type)

        label_text = (
            "Практические"
            if question_type == QuestionType.PRACTICAL
            else "Теоретические"
        )
        data_table = self._make_simple_table(
            ft.Text(label_text, overflow=ft.TextOverflow.FADE, no_wrap=True)
        )

        questions = self.sqlite.read_questions_dict(question_type)
        new_questions = get_selected_row_questions(questions, state.selected)
        textfield_storage: dict[int, str] = dict(new_questions)

        def on_textfield_change(e) -> None:
            textfield_storage[e.control.data] = e.control.value

        for cell_index, (question_id, question) in enumerate(new_questions.items()):
            teftfield = StyledTextField(
                border=ft.InputBorder.UNDERLINE,
                data=question_id,
                on_change=on_textfield_change,
                value=question,
                expand=True,
                dense=False,
                height=38,
                content_padding=ft.Padding(0, -9),
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

    def on_click_button_edit(self, e) -> None:
        has_practical = any(self._state_practical.selected.values())
        has_theoretical = any(self._state_theoretical.selected.values())

        if not has_practical and not has_theoretical:
            logging.info("Вопрос(ы) не выбран(ы)")
            self.page.show_dialog(WarnPopup("Вопрос(ы) не выбран(ы)"))
            return

        tables_data: dict[QuestionType, dict[int, str]] = {}
        table_content = ft.Row(expand=True)

        width = self.page.width * 0.90 if self.page.width else None
        self.dialog_content_edit_questions.controls = [table_content]
        self.dialog_content_edit_questions.width = width

        def fillout_questions(question_type: QuestionType) -> None:
            table, questions = self.get_questions_table_and_data(question_type)
            tables_data[question_type] = questions
            table_content.controls.append(ft.Container(expand=True, content=table))

        if has_practical:
            fillout_questions(QuestionType.PRACTICAL)
        if has_theoretical:
            fillout_questions(QuestionType.THEORETICAL)

        def on_click_button_save(
            tables_questions: dict[QuestionType, dict[int, str]], e
        ) -> None:
            for qtype, questions in tables_questions.items():
                self.sqlite.edit_questions(questions)
                self.refresh_table(qtype)
            self.page.pop_dialog()

        button_save = StyledButton(
            content=ft.Text(
                value="Сохранить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.SAVE,
            on_click=lambda e: on_click_button_save(tables_data, e),
        )
        button_close = StyledButton(
            content=ft.Text(
                value="Закрыть", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.CLOSE,
            on_click=self.page.pop_dialog,
        )

        dialog = StyledAlertDialog(
            modal=True,
            content=self.dialog_content_edit_questions,
            actions=[ft.Row([button_save, button_close])],
        )
        self.page.show_dialog(dialog)

    def on_click_button_add(self, e) -> None:
        textfields: list[list] = []
        list_view = ft.ListView(padding=14, spacing=9, expand=True)

        def add_row(e) -> None:
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

        def remove_textfield(tf) -> None:
            if len(textfields) == 1:
                return
            for item in textfields:
                if item[0] == tf:
                    textfields.remove(item)
                    list_view.controls.remove(item[1])
                    break
            self.page.update()

        add_row(None)

        segments_qtype = StyledSegmentedButton(
            selected=[QuestionType.PRACTICAL.value],
            segments=[
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
            ],
        )

        def on_click_save(e: ft.Event[ft.Button]) -> None:
            values = [tf.value.strip() for tf, _ in textfields if tf.value.strip()][
                ::-1
            ]  # reverse list

            if not values or not segments_qtype.selected:
                return

            try:
                question_type = QuestionType(next(iter(segments_qtype.selected)))
            except ValueError:
                return

            state, _ = self._get_type_state(question_type)
            self.sqlite.add_list(values, question_type)
            state.questions.clear()
            state.questions.update(self.sqlite.read_questions_dict(question_type))
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
                value="Сохранить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.SAVE,
            on_click=on_click_save,
        )
        button_close = StyledButton(
            content=ft.Text(
                value="Закрыть", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.CLOSE,
            on_click=self.page.pop_dialog,
        )

        alert_layout = StyledAlertDialog(content_padding=ft.Padding.all(0), modal=True)
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
        alert_layout.actions = [
            ft.Column(
                controls=[
                    ft.Row(expand=True, controls=[segments_qtype]),
                    ft.Row(
                        controls=[button_add_row, button_save, button_close],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ]
            )
        ]
        self.page.show_dialog(alert_layout)


class TabEditQuestions(EditQuestionsTabController):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(page, table_practical=None, table_theoretical=None)

        self.table_practical = _make_table(
            state=self._state_practical,
            label=ft.Text("Практические", overflow=ft.TextOverflow.FADE, no_wrap=True),
            question_type=QuestionType.PRACTICAL,
            sqlite=self.sqlite,
        )
        self.table_theoretical = _make_table(
            state=self._state_theoretical,
            label=ft.Text("Теоретические", overflow=ft.TextOverflow.FADE, no_wrap=True),
            question_type=QuestionType.THEORETICAL,
            sqlite=self.sqlite,
        )

        self.button_delete = StyledButton(
            content=ft.Text(
                value="Удалить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.DELETE,
            height=38,
            width=160,
            expand=2,
            on_click=self.on_click_button_delete,
        )
        self.button_add = StyledButton(
            content=ft.Text(
                value="Добавить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.ADD,
            width=160,
            height=38,
            expand=2,
            on_click=self.on_click_button_add,
        )
        self.button_edit = StyledButton(
            content=ft.Text(
                value="Изменить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            icon=ft.Icons.EDIT,
            width=160,
            height=38,
            expand=2,
            on_click=self.on_click_button_edit,
        )
        self.button_paste = StyledButton(
            content=ft.Text(
                value="Вставить", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            tooltip="Вставить",
            icon=ft.Icons.PASTE,
            on_click=self.on_click_paste,
        )
        self.button_upload_docx = StyledButton(
            content=ft.Text(
                value="Импорт", overflow=ft.TextOverflow.FADE, no_wrap=True
            ),
            tooltip="Импорт",
            icon=ft.Icons.FILE_UPLOAD,
            on_click=self.on_click_button_upload,
        )

    def get_ui(self) -> ft.Column:
        assert self.table_practical is not None, "table_practical not initialised"
        assert self.table_theoretical is not None, "table_theoretical not initialised"

        datatables = ft.Row(
            spacing=9,
            expand=True,
            controls=[self.table_practical, self.table_theoretical],
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
        return ft.Column([datatables, buttons])
