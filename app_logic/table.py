from typing import Any


def get_selected_questions(
    questions: dict[int, Any], selected_rows: dict[int, Any]
) -> dict[int, Any]:
    tmp = questions.copy()
    for key, value in selected_rows.items():
        if not value:
            tmp.pop(key)

    return tmp
