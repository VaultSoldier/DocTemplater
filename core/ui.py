import logging
import os
import platform
import subprocess


def open_file(filepath: str):
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)  # type: ignore[reportAttributeAccessIssue]
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        logging.error(f"Can't open file: {e}")
