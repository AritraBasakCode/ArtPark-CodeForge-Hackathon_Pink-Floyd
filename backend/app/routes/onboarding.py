import json
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db
from app.models.plan import PlanRecord
from app.schemas.onboarding import PlanResponse
from app.services.parser import extract_name, extract_role_title
from app.services.skill_gap import build_skill_gap
from app.services.adaptive_pathing import generate_roadmap

router = APIRouter(prefix="/api", tags=["onboarding"])


async def read_upload_text(file: UploadFile) -> str:
    content = await file.read()
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


@router.post("/generate-plan", response_model=PlanResponse)
async def generate_plan(
    resume: UploadFile = File(...),
    job_description: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    resume_text = await read_upload_text(resume)
    jd_text = await read_upload_text(job_description)

    if not resume_text.strip() or not jd_text.strip():
        raise HTTPException(status_code=400, detail="Could not read resume or job description text.")

    candidate_name = extract_name(resume_text)
    role_title = extract_role_title(jd_text)

    skill_gaps = build_skill_gap(resume_text, jd_text)
    path_result = generate_roadmap(skill_gaps)

    covered = sum(1 for s in skill_gaps if s["gap"] == 0)
    total = len(skill_gaps)
    metrics = {
        "total_jd_skills": total,
        "already_covered_skills": covered,
        "gap_skills": total - covered,
        "coverage_ratio": round((covered / total), 3) if total else 0.0
    }

    payload = {
        "candidate_name": candidate_name,
        "role_title": role_title,
        "skill_gaps": skill_gaps,
        "roadmap": path_result["roadmap"],
        "reasoning_trace": path_result["reasoning_trace"],
        "metrics": metrics
    }

    try:
        rec = PlanRecord(
            candidate_name=candidate_name,
            role_title=role_title,
            resume_text=resume_text,
            jd_text=jd_text,
            result_json=json.dumps(payload)
        )
        db.add(rec)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")

    return payload