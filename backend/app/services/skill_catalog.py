import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_course_catalog():
    with open(os.path.join(DATA_DIR, "course_catalog.json"), "r", encoding="utf-8") as f:
        return json.load(f)