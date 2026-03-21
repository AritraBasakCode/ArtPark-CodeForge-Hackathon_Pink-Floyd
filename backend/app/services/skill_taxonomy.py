import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_skill_taxonomy():
    with open(os.path.join(DATA_DIR, "skill_taxonomy.json"), "r", encoding="utf-8") as f:
        return json.load(f)