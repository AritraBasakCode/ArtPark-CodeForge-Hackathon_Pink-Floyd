import re
from typing import Dict, List, Tuple
from app.services.skill_taxonomy import load_skill_taxonomy


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_name(resume_text: str) -> str:
    first_line = resume_text.strip().splitlines()[0] if resume_text.strip() else ""
    if len(first_line.split()) <= 5:
        return first_line.strip()
    return "Candidate"


def extract_role_title(jd_text: str) -> str:
    lines = [l.strip() for l in jd_text.splitlines() if l.strip()]
    for l in lines[:8]:
        if any(k in l.lower() for k in ["engineer", "developer", "analyst", "manager", "specialist"]):
            return l
    return "Target Role"


def detect_skills(text: str) -> Dict[str, List[str]]:
    taxonomy = load_skill_taxonomy()
    t = normalize_text(text)
    found: Dict[str, List[str]] = {}

    for skill, variants in taxonomy.items():
        hits = []
        for phrase in variants:
            if re.search(rf"\b{re.escape(phrase.lower())}\b", t):
                hits.append(phrase)
        if hits:
            found[skill] = sorted(set(hits))
    return found


def estimate_candidate_level(resume_text: str, skill: str, evidence: List[str]) -> int:
    t = normalize_text(resume_text)

    years = 0
    year_patterns = [
        r"(\d+)\+?\s+years",
        r"(\d+)\+?\s+yrs",
        r"experience\s+of\s+(\d+)\s+years",
    ]
    for p in year_patterns:
        m = re.search(p, t)
        if m:
            years = max(years, int(m.group(1)))

    base = 1 if evidence else 0
    if years >= 1:
        base = max(base, 2)
    if years >= 3:
        base = max(base, 3)
    if years >= 5:
        base = max(base, 4)
    if years >= 8:
        base = 5

    if re.search(rf"\b(led|architected|owned|mentored).{{0,25}}{re.escape(skill.lower())}\b", t):
        base = min(5, base + 1)

    return min(base, 5)


def estimate_required_level(jd_text: str, skill: str, evidence: List[str]) -> Tuple[int, int]:
    t = normalize_text(jd_text)
    required_level = 3
    priority = 3

    if re.search(rf"\b(must have|required|mandatory).{{0,30}}{re.escape(skill.lower())}\b", t):
        required_level = 4
        priority = 5
    elif re.search(rf"\b(strong|expert|advanced).{{0,30}}{re.escape(skill.lower())}\b", t):
        required_level = 4
        priority = 4
    elif re.search(rf"\b(nice to have|plus|preferred).{{0,30}}{re.escape(skill.lower())}\b", t):
        required_level = 2
        priority = 2

    return required_level, priority