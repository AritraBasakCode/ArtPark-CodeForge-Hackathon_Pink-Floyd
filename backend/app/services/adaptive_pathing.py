from typing import Dict, List, Set
from app.services.skill_catalog import load_course_catalog


def topological_modules_for_skill(skill: str, catalog: Dict) -> List[Dict]:
    modules = [m for m in catalog["modules"] if m["skill_target"] == skill]
    if not modules:
        return []

    by_id = {m["module_id"]: m for m in modules}
    indeg = {m["module_id"]: 0 for m in modules}
    graph = {m["module_id"]: [] for m in modules}

    for m in modules:
        for p in m.get("prerequisites", []):
            if p in by_id:
                graph[p].append(m["module_id"])
                indeg[m["module_id"]] += 1

    queue = [mid for mid, d in indeg.items() if d == 0]
    ordered = []
    while queue:
        cur = queue.pop(0)
        ordered.append(by_id[cur])
        for nxt in graph[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    return ordered


def generate_roadmap(skill_gaps: List[Dict]) -> Dict:
    catalog = load_course_catalog()
    selected_modules = []
    trace = []
    seen: Set[str] = set()

    for gap_item in skill_gaps:
        if gap_item["gap"] <= 0:
            continue

        skill = gap_item["skill"]
        skill_modules = topological_modules_for_skill(skill, catalog)

        target_count = min(len(skill_modules), gap_item["gap"] + 1)
        picked = skill_modules[:target_count]

        for m in picked:
            if m["module_id"] in seen:
                continue
            seen.add(m["module_id"])

            utility = (gap_item["gap"] * gap_item["priority"]) / max(1, m["estimated_hours"])
            selected_modules.append((utility, m, gap_item))
            trace.append({
                "skill": skill,
                "module_id": m["module_id"],
                "reason": f"Selected for skill gap={gap_item['gap']} and priority={gap_item['priority']}",
                "utility_score": round(utility, 3),
                "grounded_catalog_ref": m["module_id"]
            })

    selected_modules.sort(key=lambda x: x[0], reverse=True)
    ordered = [x[1] for x in selected_modules]

    phases = []
    chunk_size = 3
    for i in range(0, len(ordered), chunk_size):
        chunk = ordered[i:i+chunk_size]
        modules = [{
            "module_id": m["module_id"],
            "title": m["title"],
            "skill_target": m["skill_target"],
            "estimated_hours": m["estimated_hours"],
            "why": m["why"],
            "prerequisites": m.get("prerequisites", [])
        } for m in chunk]
        phases.append({
            "phase": f"Week {len(phases)+1}",
            "total_hours": sum(m["estimated_hours"] for m in modules),
            "modules": modules
        })

    return {
        "roadmap": phases,
        "reasoning_trace": trace
    }