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
from app_logic.processing.data_operations import SqliteData, get_resource_path_temp
from app_logic.types import QuestionType


# INFO: МОЖНО ОПТИМИЗИРОВАТЬ ПЕРЕДАВАЯ ВОПРОСЫ, А НЕ ЗАГРУЖАТЬ ИХ
class Processing:
    def __init__(self) -> None:
        self.PATH_BASE_DOC: Final[str] = get_resource_path_temp(
            "assets/templates/base.docx"
        )
        self.sql = SqliteData()

        self.practical_questions: list[str] = []
        self.practical_number_of_questions: int = 0

        self.theoretical_questions: list[str] = []
        self.theoretical_number_of_questions: int = 0

        self.tmp_base = tempfile.NamedTemporaryFile(prefix="tmp_base_", suffix=".docx")

    def questions_import(self):
        self.practical_questions: list[str] = self.sql.read_questions_list(
            QuestionType.PRACTICAL
        )
        self.practical_number_of_questions: int = len(self.practical_questions)

        self.theoretical_questions: list[str] = self.sql.read_questions_list(
            QuestionType.THEORETICAL
        )
        self.theoretical_number_of_questions: int = len(self.theoretical_questions)

    def get_list_safe(
        self, items_list: list, index: int, fallback: Optional[bool] = False
    ) -> str:
        if not items_list:
            return ""

        try:
            item = items_list[index]
            return str(item)
        except IndexError:
            if fallback:
                item = str(random.choice(items_list))
                return item

            return ""

    def get_dict_safe(self, mapping: dict, index: int) -> str:
        try:
            value = mapping[index]
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
        num_of_tickets: int | None,
        qualify_status: bool | None,
        status_cards_number: str,
        status_rnd_theoretical: str,
        status_rnd_practical: str,
    ):
        """Const generator for template and entrypoint"""
        logging.info(
            f"subject: {subject}\nspec: {spec}\ncmk: {cmk}\ntutor: {tutor}\ndate: {date}\n"
        )

        # ОБНОВЛЕНИЕ ВОПРОСОВ
        self.questions_import()

        if status_cards_number == "Manual" and num_of_tickets:
            tickets = range(num_of_tickets)
        elif status_cards_number == "Practical":
            if self.practical_number_of_questions == 0:
                return "Нету практических вопросов"
            tickets = range(self.practical_number_of_questions)
        elif status_cards_number == "Theoretical":
            if self.theoretical_number_of_questions == 0:
                return "Нету теоретических вопросов"
            tickets = range(self.theoretical_number_of_questions)
        else:
            return "Неизвестная ошибка"

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
        tpl.save(self.tmp_base.name)

        if len(tickets) == 1:
            i = tickets[0]

            question_1 = self.get_selected_questions(
                QuestionType.PRACTICAL, status_rnd_practical, i
            )
            question_2 = self.get_selected_questions(
                QuestionType.THEORETICAL, status_rnd_theoretical, i
            )

            tpl_single = DocxTemplate(self.tmp_base.name)
            self.docx_save(
                question_1=question_1,
                question_2=question_2,
                ticket_num=str(i + 1),
                tmpfile=self.tmp_base,
                tpl=tpl_single,
            )
            tpl_single.save(save_to)
            return

        tmp_files = self.replace_questions(
            status_rnd_practical=status_rnd_practical,
            status_rnd_theoretical=status_rnd_theoretical,
            tickets=tickets,
        )
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

    def get_selected_questions(
        self,
        question_type: QuestionType,
        status_rnd: str,
        question_index: int,
    ):
        if question_type == QuestionType.PRACTICAL:
            questions_list = self.practical_questions
        elif question_type == QuestionType.THEORETICAL:
            questions_list = self.theoretical_questions

        if status_rnd == "always" and self.practical_questions:
            question = str(random.choice(questions_list))
        elif status_rnd == "fallback":
            question = self.get_list_safe(questions_list, question_index, True)
        elif status_rnd == "none":
            question = self.get_list_safe(questions_list, question_index)
        else:
            question = ""

        return question

    def replace_questions(
        self,
        status_rnd_practical: str,
        status_rnd_theoretical: str,
        tickets: range,
    ) -> list[tempfile._TemporaryFileWrapper]:
        """Replace questions"""

        tpl = DocxTemplate(self.tmp_base.name)
        tmpfiles = []

        for i in tickets:
            temp_file_num = f"tmp_{i}"
            tmpfile = tempfile.NamedTemporaryFile(prefix=temp_file_num, suffix=".docx")

            question_1 = self.get_selected_questions(
                QuestionType.PRACTICAL, status_rnd_practical, i
            )
            question_2 = self.get_selected_questions(
                QuestionType.THEORETICAL, status_rnd_theoretical, i
            )

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

        for idx, tmp in enumerate(tmp_paths[1:], start=1):
            doc = Document(tmp.name)
            composer.append(doc)
            if idx != len(tmp_paths) - 1:
                master.add_page_break()
        composer.save(save_to)
        self.cleaning(tmp_paths)

    def cleaning(self, paths: list[tempfile._TemporaryFileWrapper]):
        # clean temporary files
        file_path = ""
        for tmp_file in paths:
            try:
                file_path = tmp_file.name

                # Deletes files on UNIX
                # And makes sure it closes before deleting on non UNIX
                if not tmp_file.closed:
                    tmp_file.close()
                    logging.info(f"Closed temp file: {file_path}")

                # Deletes files on non UNIX systems
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted temp file: {file_path}")

            except Exception as e:
                logging.error(f"Failed to delete {file_path}: {e}")

        # clean temporary base file
        tmp_base_path = self.tmp_base.name
        if os.path.exists(tmp_base_path):
            try:
                if not self.tmp_base.closed:
                    logging.info(f"Closed temp base file: {tmp_base_path}")
                    self.tmp_base.close()

                if os.path.exists(tmp_base_path):
                    os.remove(tmp_base_path)
                    logging.info(f"Deleted temp file: {tmp_base_path}")

            except Exception as e:
                logging.error(f"Failed to delete {self.tmp_base.name}: {e}")
