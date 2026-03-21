from typing import List, Dict
from app.services.parser import detect_skills, estimate_candidate_level, estimate_required_level


def build_skill_gap(resume_text: str, jd_text: str) -> List[Dict]:
    candidate_skills = detect_skills(resume_text)
    jd_skills = detect_skills(jd_text)

    all_jd_skills = list(jd_skills.keys())
    gaps: List[Dict] = []

    for skill in all_jd_skills:
        candidate_evidence = candidate_skills.get(skill, [])
        jd_evidence = jd_skills.get(skill, [])

        candidate_level = estimate_candidate_level(resume_text, skill, candidate_evidence)
        required_level, priority = estimate_required_level(jd_text, skill, jd_evidence)
        gap = max(0, required_level - candidate_level)

        gaps.append({
            "skill": skill,
            "candidate_level": candidate_level,
            "required_level": required_level,
            "gap": gap,
            "priority": priority,
            "evidence": candidate_evidence + jd_evidence
        })

    gaps.sort(key=lambda x: (x["gap"] * x["priority"], x["priority"]), reverse=True)
    return gaps