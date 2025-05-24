import os
import logging
import random
import tempfile
import math
from typing import Final, Optional
from docx.enum.text import WD_BREAK
from docxtpl import DocxTemplate, RichText
from docx import Document
from docxcompose.composer import Composer
from app_logic.processing.data_operations import SqliteData, get_resource_path
from app_logic.types import QuestionType


# INFO: МОЖНО ОПТИМИЗИРОВАТЬ ПЕРЕДАВАЯ ВОПРОСЫ, А НЕ ЗАГРУЖАТЬ ИХ
class Processing:
    def __init__(self) -> None:
        self.PATH_BASE_DOC: Final[str] = get_resource_path("assets/templates/base.docx")
        self.sql = SqliteData()

        self.practical_questions: list[str] = []
        self.practical_number_of_questions: int = 0

        self.theoretical_questions: list[str] = []
        self.theoretical_number_of_questions: int = 0

        self.path_tmp_base = tempfile.NamedTemporaryFile(
            prefix="tmp_base_", suffix=".docx", delete=True
        )

    def questions_import(self):
        self.practical_questions: list[str] = self.sql.read_questions_list(
            QuestionType.PRACTICAL
        )
        self.practical_number_of_questions: int = len(self.practical_questions)

        self.theoretical_questions: list[str] = self.sql.read_questions_list(
            QuestionType.THEORETICAL
        )
        self.theoretical_number_of_questions: int = len(self.theoretical_questions)

    def get_list_safe(self, items_list: list, index: int):
        try:
            return items_list[index]
        except IndexError:
            return ""

    def get_dict_safe(self, dict: dict, index: int) -> str:
        try:
            value = dict[index]
        except KeyError:
            value = ""
        return value

    def generate_document(
        self,
        save_to: str,
        subject: str,
        spec: str,
        cmk: str,
        tutor: str,
        date: list,
        qualify_status: bool | None,
        random_simple_question: bool | None,
        random_hard_question: bool | None,
    ):
        """Const generator for template and entrypoint"""
        logging.info(
            f"subject: {subject}\nspec: {spec}\ncmk: {cmk}\ntutor: {tutor}\ndate: {date}\n"
        )

        # ОБНОВЛЕНИЕ ВОПРОСОВ
        self.questions_import()

        day = date[2] or "__"
        month = date[1] or ""
        year = date[0] or ""

        if qualify_status:
            qualify = " (квалификационный)"
        else:
            qualify = ""

        if day in range(0, 10):
            day = "0" + str(day)

        rt_day = RichText()
        rt_month = RichText()
        rt_day.add(day, underline=True)

        total_width = 16
        padding = total_width - len(str(month))
        left_pad = " " * (padding // 2)
        right_pad = " " * math.ceil(padding / 2)

        rt_month.add(left_pad)
        rt_month.add(month, underline="thick", bold=True)  # type: ignore[assignment]
        rt_month.add(right_pad)

        context = {
            "qualify": qualify,
            "subject": subject,
            "spec": spec,
            "cmk": cmk,
            "tutor": tutor,
            "day": rt_day,
            "month": rt_month,
            "year": year,
            "ticket_num": "{{ticket_num}}",
            "question_1": "{{question_1}}",
            "question_2": "{{question_2}}",
        }

        tpl = DocxTemplate(self.PATH_BASE_DOC)
        tpl.render(context)
        tpl.save(self.path_tmp_base.name)

        tmp_files = self.replace_questions(random_simple_question, random_hard_question)
        self.document_merge(tmp_files, save_to)

    def docx_save(
        self, question_1: str, question_2: str, ticket_num: str, tmpfile, tpl
    ) -> None:
        logging.info(f"Ticket {ticket_num}: Q1='{question_1}', Q2='{question_2}'")

        context = {
            "ticket_num": ticket_num,
            "question_1": question_1,
            "question_2": question_2,
        }

        tpl.render(context)
        tpl.save(tmpfile.name)

    def replace_questions(
        self, random_simple_question: bool | None, random_hard_question: bool | None
    ) -> list[tempfile._TemporaryFileWrapper]:
        """Replace questions"""
        tpl = DocxTemplate(self.path_tmp_base.name)
        tmpfiles = []
        for i in range(self.practical_number_of_questions):
            temp_file_num = f"tmp_{i}"
            tmpfile = tempfile.NamedTemporaryFile(
                prefix=temp_file_num, suffix=".docx", delete=True
            )

            if random_simple_question and self.practical_questions:
                question_1 = str(random.choice(self.practical_questions))
            else:
                question_1 = str(self.practical_questions[i])

            if random_hard_question and self.theoretical_questions:
                question_2 = str(random.choice(self.theoretical_questions))
            else:
                question_raw = self.get_list_safe(self.theoretical_questions, i)
                question_2 = str(question_raw)

            self.docx_save(
                question_1=str(question_1),
                question_2=str(question_2),
                ticket_num=str(i + 1),
                tmpfile=tmpfile,
                tpl=tpl,
            )
            tmpfiles.append(tmpfile)
        return tmpfiles

    def document_merge(
        self,
        tmp_paths: list[tempfile._TemporaryFileWrapper],
        save_to: Optional[str] = None,
    ) -> None:
        """Merge all temporary files and call cleaning of tmp files"""
        master = Document(tmp_paths[0])
        composer = Composer(master)

        # master file page break
        master.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

        for ticket in range(1, self.practical_number_of_questions):
            doc = Document(tmp_paths[ticket])

            if ticket != (self.practical_number_of_questions - 1):
                doc.add_page_break()

            composer.append(doc)

        composer.save(save_to)
        self.cleaning(tmp_paths)

    def cleaning(self, paths: list[tempfile._TemporaryFileWrapper]):
        file_path = ""
        for temp_file in paths:
            try:
                file_path = temp_file.name

                if not temp_file.closed:
                    temp_file.close()

                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted temporary file: {file_path}")

            except Exception as e:
                logging.error(f"Failed to delete {file_path}: {e}")
