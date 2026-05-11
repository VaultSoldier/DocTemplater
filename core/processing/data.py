import logging
import os
import re
import sqlite3
import sys
from typing import Any, Final, List

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
        ["specialtie_id", "subject_id"],
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
            if row is None:
                raise RuntimeError("Settings not initialised - call _init() first")
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
        CREATE TABLE IF NOT EXISTS sync_etags (
            endpoint TEXT PRIMARY KEY,
            etag     TEXT NOT NULL
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
            specialtie_id INTEGER NOT NULL,
            subject_id    INTEGER NOT NULL,
            PRIMARY KEY (specialtie_id, subject_id)
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

        try:
            with sqlite3.connect(self.filepath) as conn:
                cur = conn.cursor()
                row = cur.execute("SELECT api_base FROM settings").fetchone()
                api_base: str | None = row[0] if row else None

                if not api_base:
                    self.last_status = AppEvent.API_NO_URL
                    self.page.pubsub.send_all(self.last_status)
                    logging.info("Stopping sync, no API URL...")
                    return

                for table, endpoint, columns in TABLES:
                    logging.info(f"Syncing table: {table}")
                    self.sync_table(
                        conn,
                        table,
                        api_base,
                        endpoint,
                        columns,
                    )

            logging.info("Sync completed successfully")
            self.last_status = AppEvent.API_SYNCED
            self.page.pubsub.send_all(self.last_status)

        except requests.RequestException as e:
            logging.exception(f"API error: {e}")
            self.last_status = AppEvent.API_ERROR
            self.page.pubsub.send_all(self.last_status)

        except Exception as e:
            logging.exception(f"Unexpected sync error: {e}")
            self.last_status = AppEvent.API_ERROR
            self.page.pubsub.send_all(self.last_status)

    def sync_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        api_base: str,
        endpoint: str,
        columns: List[str],
    ):
        records = self.fetch(conn, api_base, endpoint)
        if records is None:  # only skip on 304
            logging.info(f"{table}: not modified, skipping saving")
            return
        if not records:
            logging.info(f"{table}: server returned empty list")

        has_id = "id" in columns
        remote_ids: set[int] = set()

        if has_id:
            records = [r for r in records if r.get("id") is not None]
            remote_ids = {r["id"] for r in records}

        col_list = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)

        if has_id:
            updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")
            conn.executemany(
                f"""
                INSERT INTO {table} ({col_list})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {updates}
                """,
                records,
            )
            local_ids = {row[0] for row in conn.execute(f"SELECT id FROM {table}")}
            deleted_ids = local_ids - remote_ids
            if deleted_ids:
                conn.executemany(
                    f"DELETE FROM {table} WHERE id = ?", [(i,) for i in deleted_ids]
                )
        else:
            conn.execute(f"DELETE FROM {table}")
            conn.executemany(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
                records,
            )

        logging.info(f"{table}: {len(records)} upserted")

    def _save_etag(self, conn, endpoint: str, etag: str):
        conn.execute(
            """
            INSERT INTO sync_etags (endpoint, etag) VALUES (?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET etag = excluded.etag
            """,
            (endpoint, etag),
        )

    def fetch(
        self, conn: sqlite3.Connection, api_base: str, endpoint: str
    ) -> list[dict] | None:
        url = f"{api_base}{endpoint}"

        # Load ETag from the same DB as the data
        row = conn.execute(
            "SELECT etag FROM sync_etags WHERE endpoint = ?", (endpoint,)
        ).fetchone()

        headers = {"If-None-Match": row[0]} if row else {}
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code == 304:
            logging.info(f"{endpoint}: not modified, skipping fetch")
            return None

        resp.raise_for_status()

        if new_etag := resp.headers.get("ETag"):
            self._save_etag(conn, endpoint, new_etag)  # same transaction as data

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
        order_type: OrderType = OrderType.DESC,
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

    def read_subjects(self) -> list[tuple[int, str]]:
        with sqlite3.connect(self.filepath) as conn:
            return conn.execute(
                "SELECT id, name FROM subjects ORDER BY name"
            ).fetchall()

    def read_all_specialties(self) -> list[tuple[int, str]]:
        with sqlite3.connect(self.filepath) as conn:
            return conn.execute(
                "SELECT id, name FROM specialtie ORDER BY name"
            ).fetchall()

    def read_specialties_by_subject(self, subject_id: int) -> list[tuple[int, str]]:
        with sqlite3.connect(self.filepath) as conn:
            return conn.execute(
                """
                SELECT s.id, s.name
                FROM specialtie s
                JOIN specialtie_subject_link l ON l.specialtie_id = s.id
                WHERE l.subject_id = ?
                ORDER BY s.name
                """,
                (subject_id,),
            ).fetchall()

    def read_chairman_cmk(self) -> list[tuple[int, str]]:
        with sqlite3.connect(self.filepath) as conn:
            return conn.execute(
                "SELECT id, name FROM chairman_cmk ORDER BY name"
            ).fetchall()

    def read_teachers(self) -> list[tuple[int, str]]:
        with sqlite3.connect(self.filepath) as conn:
            return conn.execute("SELECT id, name FROM teacher ORDER BY name").fetchall()


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
