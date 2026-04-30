import logging
import os
import re
import sqlite3
import sys
from typing import Any, Final

import flet as ft
import requests
from docx2python import docx2python
from platformdirs import user_data_dir

from core.types import AppEvent, OrderType, QuestionType

APP_NAME: Final[str] = "DocTemplater"
APP_AUTHOR: Final[str] = "JonhSmith"
TABLES = [
    (
        "subjects",
        "/subjects/",
        ["id", "name"],
    ),
    (
        "specialtie",
        "/specialtie/",
        ["id", "name"],
    ),
    (
        "specialtie_subject_link",
        "/specialtie_subject_link/",
        ["id", "specialtie_id", "subject_id"],
    ),
    (
        "chairman_cmk",
        "/chairman_cmk/",
        ["id", "name"],
    ),
    (
        "teacher",
        "/teacher/",
        ["id", "name"],
    ),
]


def get_resource_path_temp(relative_path: str) -> str:
    """
    Возвращает корректный путь к файлу:
    - во время разработки: os.path.abspath(relative_path)
    - бинарник: берёт файлы из временной папки sys._MEIPASS
    """
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class AppSettings:
    def __init__(self):
        data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
        os.makedirs(data_dir, exist_ok=True)
        self.filepath = os.path.join(data_dir, "data.db")

    def load(self) -> dict:
        with sqlite3.connect(self.filepath) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
            return dict(row)

    def save(self, **kwargs):
        current = self.load()
        current.update(kwargs)
        with sqlite3.connect(self.filepath) as conn:
            conn.execute(
                """UPDATE settings SET api_base=?, theme_mode=? WHERE id=1""",
                (current["api_base"], current["theme_mode"]),
            )


class InitDatabase:
    SETTINGS_DEFAULTS: Final = {
        "theme_mode": "system",
    }
    SCHEMA: Final = """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            theme_mode TEXT NOT NULL,
            api_base TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            question_type TEXT CHECK (question_type IN ('theory', 'practice'))
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS specialtie (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS specialtie_subject_link (
            id            INTEGER PRIMARY KEY,
            specialtie_id INTEGER,
            subject_id    INTEGER
        );
        CREATE TABLE IF NOT EXISTS chairman_cmk (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teacher (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
    """

    def __init__(self, page: ft.Page):
        data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
        os.makedirs(data_dir, exist_ok=True)
        self.filepath = os.path.join(data_dir, "data.db")
        self.page = page
        self.last_status = None

    def _init(self):
        with sqlite3.connect(self.filepath) as conn:
            conn.executescript(self.SCHEMA)
            conn.execute(
                """INSERT OR IGNORE INTO settings (id, theme_mode)
                            VALUES (1, :theme_mode)""",
                self.SETTINGS_DEFAULTS,
            )
        self._sync_all()

    def _sync_all(self):
        logging.info("Starting sync...")

        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = "SELECT api_base FROM settings"
            row = cur.execute(sql).fetchone()
            api_base: str | None = row[0] if row else None

            if not api_base:
                self.last_status = AppEvent.API_NO_URL
                self.page.pubsub.send_all(self.last_status)
                logging.info("Stopping sync, no API URL...")
                return

            for table, endpoint, columns in TABLES:
                try:
                    self.sync_table(conn, table, api_base, endpoint, columns)
                except requests.RequestException as e:
                    self.last_status = AppEvent.API_ERROR
                    self.page.pubsub.send_all(self.last_status)
                    logging.error(f"{table}: API error — {e}")
                except Exception as e:
                    self.last_status = AppEvent.API_ERROR
                    self.page.pubsub.send_all(self.last_status)
                    logging.error(f"{table}: unexpected error — {e}")
                    raise  # re-raise to trigger rollback

    def sync_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        api_base: str,
        endpoint: str,
        columns: list[str],
    ):
        records = self.fetch(api_base, endpoint)

        if not records:
            logging.info(f"{table}: no records from API, skipping")
            return

        # Filter out records with null id
        records = [r for r in records if r.get("id") is not None]
        remote_ids = {r["id"] for r in records}

        # Upsert all remote records
        col_list = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")

        conn.executemany(
            f"""
            INSERT INTO {table} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            records,
        )

        # Delete local rows that no longer exist remotely
        local_ids = {row[0] for row in conn.execute(f"SELECT id FROM {table}")}
        deleted_ids = local_ids - remote_ids
        if deleted_ids:
            conn.executemany(
                f"DELETE FROM {table} WHERE id = ?", [(i,) for i in deleted_ids]
            )
        logging.info(f"{table}: {len(records)} upserted, {len(deleted_ids)} deleted")

    def fetch(self, api_base, endpoint: str) -> list[dict]:
        url = f"{api_base}{endpoint}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def reset_db(self):
        with sqlite3.connect(self.filepath) as conn:
            cursor = conn.cursor()
            for obj_type in ("trigger", "view", "index", "table"):
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = ? AND name NOT LIKE 'sqlite_%'
                    """,
                    (obj_type,),
                )
                for (name,) in cursor.fetchall():
                    cursor.execute(f'DROP {obj_type.upper()} IF EXISTS "{name}"')

        logging.info("Database reset complete")
        self._init()


class SqliteData:
    def __init__(self) -> None:
        data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
        os.makedirs(data_dir, exist_ok=True)
        self.filepath = os.path.join(data_dir, "data.db")

    def add_line(self, line: str, question_type: QuestionType):
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            if not isinstance(line, str) or len(line.strip()) == 0:
                raise ValueError(f"Wrong type: {type(line)}")

            sql = "INSERT INTO questions(question, question_type) VALUES(?,?)"
            cur.execute(sql, (line.strip(), question_type.value))

    def add_list(self, rows: list[str], question_type: QuestionType):
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            validated = []
            for question in rows:
                if not isinstance(question, str):
                    raise ValueError(f"Invalid question: {question}")
                elif len(question.strip()) == 0:
                    raise ValueError("Empty line")
                validated.append((question.strip(), question_type.value))
            sql = "INSERT INTO questions(question, question_type) VALUES(?,?)"
            cur.executemany(sql, validated)

    def edit_questions(self, questions: dict[int, str]):
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = "UPDATE questions SET question=? WHERE id=?"
            params = [(question, idx) for idx, question in questions.items()]
            cur.executemany(sql, params)

    def remove_by_id(self, id: int):
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = "DELETE FROM questions WHERE id=?"
            params = (id,)
            cur.execute(sql, params)

    def read_questions_dict(
        self,
        question_type: QuestionType,
        order_type: OrderType = OrderType.ASC,
    ) -> dict[int, str | int | float]:
        """
        Возвращает dict[ключ, вопрос]

        Sqlite может вернуть int или float,
        если в строку бд записано только число.
        """

        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT id, question
                FROM questions
                WHERE question_type = ?
                ORDER BY id {order_type.value}
            """
            result = cur.execute(sql, (question_type.value,))
            return {row[0]: row[1] for row in result}

    def read_questions_list(
        self,
        question_type: QuestionType,
        order_type: OrderType = OrderType.DESC,
    ) -> list[Any]:
        """
        Sqlite может вернуть int или float,
        если в строку бд записано только число.
        """
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT question
                FROM questions
                WHERE question_type = ?
                ORDER BY id {order_type.value}
            """
            result = cur.execute(sql, (question_type.value,))
            rows = result.fetchall()
            return [row[0] for row in rows]

    def has_questions(self, question_type: QuestionType) -> bool:
        with sqlite3.connect(self.filepath) as conn:
            cur = conn.cursor()
            sql = """
                SELECT 1
                FROM questions
                WHERE question_type = ?
                LIMIT 1
            """
            return cur.execute(sql, (question_type.value,)).fetchone() is not None


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
    # INFO: 1) Lorem Ipsum
    REGEX_NUM_AND_BRACKET_WITH_TEXT: Final[str] = r"\s*\d+\).*"
    # INFO: 1)
    REGEX_NUM_AND_BRACKET: Final[str] = r"\s*\d+\)"

    with docx2python(docx_path) as docx_content:
        document_text_list = re.sub(r"\t", "", (docx_content.text).replace("\t", ""))
        questions_raw = re.findall(
            REGEX_NUM_AND_BRACKET_WITH_TEXT,
            document_text_list,
        )
        questions = [
            cleaned
            for q in questions_raw
            if (cleaned := clean_question_by_regex(REGEX_NUM_AND_BRACKET, q)) != ""
        ]
    return questions
