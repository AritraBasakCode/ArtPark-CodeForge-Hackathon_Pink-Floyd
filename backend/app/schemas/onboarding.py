from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SkillItem(BaseModel):
    skill: str
    candidate_level: int
    required_level: int
    gap: int
    priority: int
    evidence: List[str]


class ModuleItem(BaseModel):
    module_id: str
    title: str
    skill_target: str
    estimated_hours: int
    why: str
    prerequisites: List[str]


class PhaseItem(BaseModel):
    phase: str
    total_hours: int
    modules: List[ModuleItem]


class PlanResponse(BaseModel):
    candidate_name: Optional[str] = None
    role_title: Optional[str] = None
    skill_gaps: List[SkillItem]
    roadmap: List[PhaseItem]
    reasoning_trace: List[Dict[str, Any]]
    metrics: Dict[str, Any]