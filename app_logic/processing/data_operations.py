import os
import re
import sqlite3
import sys
from typing import Any, Final

from docx2python import docx2python

from app_logic.types import OrderType, QuestionType


def get_resource_path(relative_path: str) -> str:
    """
    Возвращает корректный путь к файлу:
    - во время разработки: os.path.abspath(relative_path)
    - бинарник: берёт файлы из временной папки sys._MEIPASS
    """
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SqliteData:
    def __init__(self) -> None:
        self.filepath = get_resource_path("assets/data.db")
        self.con = sqlite3.connect(database=self.filepath, autocommit=True)
        self.cur = self.con.cursor()

        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY,
                question UNICODE NOT NULL,
                question_type TEXT CHECK (question_type IN ('theory', 'practice'))
            )
            """)

    def add_line(self, line: str, question_type: QuestionType):
        if not isinstance(line, str) or len(line.strip()) == 0:
            raise ValueError(f"Wrong type: {type(line)}")

        sql = "INSERT INTO questions(question, question_type) VALUES(?,?)"
        self.cur.execute(sql, (line.strip(), question_type.value))

    def add_list(self, rows: list[str], question_type: QuestionType):
        validated = []
        for question in rows:
            if not isinstance(question, str):
                raise ValueError(f"Invalid question: {question}")
            elif len(question.strip()) == 0:
                raise ValueError("Empty line")

            validated.append((question.strip(), question_type.value))

        sql = "INSERT INTO questions(question, question_type) VALUES(?,?)"
        self.cur.executemany(sql, validated)

    def edit_questions(self, questions: dict[int, str]):
        sql = "UPDATE questions SET question=? WHERE id=?"
        params = [(question, idx) for idx, question in questions.items()]
        self.cur.executemany(sql, params)

    def remove_by_id(self, id: int):
        sql = "DELETE FROM questions WHERE id=?"
        params = (id,)
        self.cur.execute(sql, params)

    def read_questions_dict(
        self, question_type: QuestionType, order_type: OrderType = OrderType.DESC
    ) -> dict[int, str | int | float]:
        """
        Возвращает dict[ключ, вопрос]

        Sqlite может вернуть int или float, если в строку бд записано только число.
        """

        sql = f"""
            SELECT id, question 
            FROM questions 
            WHERE question_type = ?
            ORDER BY id {order_type.value}
        """
        result = self.cur.execute(sql, (question_type.value,))
        return {row[0]: row[1] for row in result}

    def read_questions_list(
        self, question_type: QuestionType, order_type: OrderType = OrderType.DESC
    ) -> list[Any]:
        """
        Возвращает list[вопрос]

        Sqlite может вернуть int или float, если в строку бд записано только число.
        """

        sql = f"""
            SELECT question 
            FROM questions 
            WHERE question_type = ?
            ORDER BY id {order_type.value}
        """

        result = self.cur.execute(sql, (question_type.value,))
        rows = result.fetchall()
        return [row[0] for row in rows]


class TextProcessing:
    def get_dict(self, filepath: str) -> list[str] | None:
        REGEX = r"^\s*\d+[.)]{1,2}\s*"  # пример: 1) или 1. или 1.)

        with open(filepath, "r", encoding="utf-8") as file:
            values = [
                cleaned
                for q in file
                if (cleaned := clean_question_by_regex(REGEX, q)) != ""
            ]

            if not any(values):
                return

            return values


def clean_question_by_regex(regex, question: str) -> str:
    return re.sub(regex, "", question.strip()).strip()


def docx_extract_questions(docx_path: str) -> list[str]:
    """Return all numbered text from .docx"""
    REGEX_NUMBER_WITH_BRACKET_LINE: Final[str] = r"\s*\d+\).*"  # example: 1)Lorem
    REGEX_NUMBER_WITH_BRACKET: Final[str] = r"\s*\d+\)"  # example: 1)

    with docx2python(docx_path) as docx_content:
        document_text_list = re.sub(r"\t", "", (docx_content.text).replace("\t", ""))
        questions_raw = re.findall(REGEX_NUMBER_WITH_BRACKET_LINE, document_text_list)

        questions = [
            cleaned
            for q in questions_raw
            if (cleaned := clean_question_by_regex(REGEX_NUMBER_WITH_BRACKET, q)) != ""
        ]

    return questions
