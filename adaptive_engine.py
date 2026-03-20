"""
adaptive_engine.py
------------------
The original adaptive pathing algorithm.

Three components:
  1. Skill extractor  — pulls skill keywords + proficiency from resume/JD text
  2. Gap scorer       — computes urgency score per skill
  3. Adaptive pather  — DAG + topological sort → ordered learning pathway

Usage:
    from adaptive_engine import AdaptiveEngine

    engine = AdaptiveEngine()
    pathway = engine.generate_pathway(resume_text, jd_text)

    for module in pathway:
        print(module)
"""

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. SKILL TAXONOMY
#    The master list of known skills, grouped by domain.
#    You can expand this freely — the more skills, the better the matching.
# ---------------------------------------------------------------------------

SKILL_TAXONOMY = {
    "languages": [
        "Python", "JavaScript", "TypeScript", "Java", "Scala", "R",
        "C++", "C#", "Go", "Rust", "SQL", "Bash", "MATLAB"
    ],
    "ml_core": [
        "Machine Learning", "Deep Learning", "Neural Networks",
        "Supervised Learning", "Unsupervised Learning", "Reinforcement Learning",
        "NLP", "Computer Vision", "Time Series", "Feature Engineering",
        "Model Evaluation", "Hyperparameter Tuning", "Cross Validation"
    ],
    "ml_frameworks": [
        "PyTorch", "TensorFlow", "Keras", "Scikit-learn", "XGBoost",
        "LightGBM", "Hugging Face", "Transformers", "spaCy", "NLTK",
        "OpenCV", "FastAI"
    ],
    "data": [
        "NumPy", "Pandas", "Matplotlib", "Seaborn", "Plotly",
        "Spark", "Kafka", "Airflow", "dbt", "Snowflake",
        "BigQuery", "Redshift", "Databricks"
    ],
    "mlops": [
        "MLflow", "Kubeflow", "Weights & Biases", "DVC", "BentoML",
        "Seldon", "Model Monitoring", "A/B Testing", "Feature Store",
        "CI/CD", "Model Versioning"
    ],
    "cloud": [
        "AWS", "GCP", "Azure", "SageMaker", "Vertex AI",
        "Lambda", "EC2", "S3", "BigQuery", "Dataflow",
        "Docker", "Kubernetes", "Terraform", "Helm"
    ],
    "databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Cassandra", "DynamoDB", "SQLite", "Neo4j"
    ],
    "webdev": [
        "React", "Next.js", "Vue", "Angular", "Node.js",
        "FastAPI", "Django", "Flask", "Express", "GraphQL",
        "REST", "REST APIs", "HTML", "CSS", "Tailwind"
    ],
    "statistics": [
        "Statistics", "Probability", "Bayesian Inference",
        "Hypothesis Testing", "Linear Algebra", "Calculus",
        "Regression", "Classification", "Clustering"
    ],
    "tools": [
        "Git", "GitHub", "Jira", "Linux", "VS Code",
        "Jupyter", "Postman", "Figma", "Agile", "Scrum"
    ],
}

# Flat list of all skills for fast lookup
ALL_SKILLS = [skill for skills in SKILL_TAXONOMY.values() for skill in skills]

# Which domain each skill belongs to
SKILL_TO_DOMAIN = {
    skill: domain
    for domain, skills in SKILL_TAXONOMY.items()
    for skill in skills
}


# ---------------------------------------------------------------------------
# 2. PREREQUISITE GRAPH (DAG)
#    key   = skill that has prerequisites
#    value = list of skills that must be learned first
#
#    This is YOUR original contribution — you define the learning order.
# ---------------------------------------------------------------------------

PREREQUISITE_GRAPH = {
    # Data science stack
    "NumPy":              ["Python"],
    "Pandas":             ["Python", "NumPy"],
    "Matplotlib":         ["Python", "NumPy"],
    "Seaborn":            ["Matplotlib", "Pandas"],
    "Plotly":             ["Python", "Pandas"],

    # ML core
    "Scikit-learn":       ["Python", "NumPy", "Pandas", "Statistics"],
    "Machine Learning":   ["Python", "Statistics", "NumPy"],
    "Feature Engineering":["Pandas", "Scikit-learn"],
    "Model Evaluation":   ["Scikit-learn", "Statistics"],
    "Hyperparameter Tuning": ["Scikit-learn", "Model Evaluation"],
    "Cross Validation":   ["Scikit-learn"],

    # Deep learning stack
    "PyTorch":            ["Python", "NumPy", "Machine Learning"],
    "TensorFlow":         ["Python", "NumPy", "Machine Learning"],
    "Keras":              ["TensorFlow"],
    "Deep Learning":      ["PyTorch", "Linear Algebra"],
    "Neural Networks":    ["Deep Learning"],
    "Computer Vision":    ["Deep Learning", "NumPy", "OpenCV"],
    "NLP":                ["Python", "Deep Learning"],
    "Transformers":       ["Deep Learning", "NLP"],
    "Hugging Face":       ["Transformers", "PyTorch"],
    "spaCy":              ["Python", "NLP"],

    # MLOps
    "MLflow":             ["Scikit-learn", "Python"],
    "Model Monitoring":   ["MLflow", "Model Evaluation"],
    "A/B Testing":        ["Statistics", "Model Evaluation"],
    "Feature Store":      ["Feature Engineering", "MLflow"],
    "Model Versioning":   ["MLflow"],
    "DVC":                ["Git", "Python"],
    "CI/CD":              ["Git", "Docker"],
    "Kubeflow":           ["Kubernetes", "MLflow"],

    # Cloud + infra
    "Docker":             ["Linux", "Bash"],
    "Kubernetes":         ["Docker"],
    "Terraform":          ["Cloud"],
    "SageMaker":          ["AWS", "Machine Learning", "Docker"],
    "Vertex AI":          ["GCP", "Machine Learning"],
    "Lambda":             ["AWS", "Python"],

    # Stats prereqs
    "Regression":         ["Statistics", "Linear Algebra"],
    "Classification":     ["Regression", "Scikit-learn"],
    "Clustering":         ["Statistics", "Scikit-learn"],
    "Bayesian Inference": ["Statistics", "Probability"],
    "Hypothesis Testing": ["Statistics", "Probability"],

    # Data engineering
    "Spark":              ["Python", "SQL"],
    "Airflow":            ["Python", "Docker"],
    "Kafka":              ["Python", "Linux"],
    "dbt":                ["SQL", "Python"],
    "Databricks":         ["Spark", "Python"],

    # Web
    "React":              ["JavaScript", "HTML", "CSS"],
    "Next.js":            ["React"],
    "Vue":                ["JavaScript", "HTML", "CSS"],
    "Node.js":            ["JavaScript"],
    "FastAPI":            ["Python", "REST APIs"],
    "Django":             ["Python", "SQL"],
    "Flask":              ["Python"],
    "GraphQL":            ["REST APIs"],
    "TypeScript":         ["JavaScript"],
}


# ---------------------------------------------------------------------------
# 3. PROFICIENCY SIGNALS
#    Patterns in resume text that indicate experience level for a skill.
# ---------------------------------------------------------------------------

PROFICIENCY_SIGNALS = [
    # High proficiency (70-90)
    (r"\b(\d+)\+?\s*years?\s*(of\s*)?(experience\s*(with|in|using)?\s*)?{skill}", 0),   # "5 years Python"
    (r"\b(lead|led|architect|designed|built|expert|senior)\b.*\b{skill}\b", 85),
    (r"\b{skill}\b.*\b(lead|led|architect|designed|built|expert)\b", 85),
    (r"\b(proficient|advanced|strong|extensive)\s*(in|with)?\s*{skill}\b", 80),
    (r"\b{skill}\b.*\(proficient\)", 80),

    # Medium proficiency (40-65)
    (r"\b(intermediate|working\s*knowledge|familiar|experienced)\s*(with|in)?\s*{skill}\b", 60),
    (r"\b{skill}\b.*\(intermediate\)", 55),
    (r"\bused?\s*{skill}\b", 55),
    (r"\b{skill}\b.*\bprojects?\b", 55),

    # Low proficiency (15-35)
    (r"\b(basic|beginner|learning|exposure|some\s*experience)\s*(with|in)?\s*{skill}\b", 25),
    (r"\b{skill}\b.*\(basic\)", 20),
    (r"\bfamiliarity\s*(with)?\s*{skill}\b", 30),
    (r"\b(studying|learning)\s*{skill}\b", 20),
]

# JD signals that indicate how required a skill is
CRITICALITY_SIGNALS = [
    (r"\b(required|must\s*have|essential|mandatory)\b.*\b{skill}\b", 1.5),
    (r"\b{skill}\b.*\b(required|must\s*have|essential|mandatory)\b", 1.5),
    (r"\b\d\+?\s*years?\s*(of\s*)?{skill}\b", 1.5),        # "3+ years Python"
    (r"\b(strong|deep|expert|advanced)\s*(knowledge\s*of|experience\s*(with|in))?\s*{skill}\b", 1.3),
    (r"\b(preferred|nice\s*to\s*have|plus|bonus)\b.*\b{skill}\b", 0.5),
    (r"\b{skill}\b.*\b(preferred|nice\s*to\s*have|plus|bonus)\b", 0.5),
    (r"\b(familiarity|exposure|basic\s*knowledge)\s*(with|of)?\s*{skill}\b", 0.7),
]

DEFAULT_CANDIDATE_LEVEL = 50   # if skill is listed but no signal found
DEFAULT_REQUIRED_LEVEL  = 70   # if skill appears in JD but no level specified
DEFAULT_CRITICALITY     = 1.0  # if no criticality signal found


# ---------------------------------------------------------------------------
# 4. DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class CandidateSkill:
    name:   str
    level:  int          # 0–100
    domain: str
    source: str          # which text triggered this


@dataclass
class RequiredSkill:
    name:            str
    required_level:  int     # 0–100
    criticality:     float   # 0.5 / 1.0 / 1.3 / 1.5
    domain:          str


@dataclass
class GapSkill:
    name:          str
    domain:        str
    candidate_level: int
    required_level:  int
    gap:           int       # required - candidate (always > 0)
    criticality:   float
    urgency_score: float     # gap × criticality — YOUR formula
    is_prerequisite: bool = False   # True if added by DAG, not direct gap


@dataclass
class PathwayModule:
    order:           int
    skill:           str
    domain:          str
    urgency_score:   float
    candidate_level: int
    required_level:  int
    gap:             int
    is_prerequisite: bool
    duration_weeks:  int
    priority:        str     # critical / high / medium / low


# ---------------------------------------------------------------------------
# 5. SKILL EXTRACTOR
# ---------------------------------------------------------------------------

class SkillExtractor:
    """
    Extracts skills from raw text using keyword matching + signal detection.
    Works on both resume text (returns CandidateSkill list)
    and JD text (returns RequiredSkill list).
    """

    def _find_skills_in_text(self, text: str) -> list[str]:
        """Find all skill keywords present in the text."""
        found = []
        text_lower = text.lower()
        for skill in ALL_SKILLS:
            # Use word boundary matching, case-insensitive
            pattern = r'\b' + re.escape(skill.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.append(skill)
        return found

    def _detect_proficiency(self, text: str, skill: str) -> tuple[int, str]:
        """
        Detect proficiency level from context around a skill mention.
        Returns (level 0-100, source description).
        """
        text_lower = text.lower()
        skill_lower = skill.lower()

        for pattern_template, fixed_level in PROFICIENCY_SIGNALS:
            pattern = pattern_template.replace("{skill}", re.escape(skill_lower))
            match = re.search(pattern, text_lower)
            if match:
                if fixed_level == 0:
                    # Extract years from the match
                    years_match = re.search(r'(\d+)', match.group())
                    if years_match:
                        years = int(years_match.group())
                        level = min(95, 40 + (years * 9))  # 1yr=49, 5yr=85, 10yr=95
                        return level, f"{years} years experience"
                else:
                    return fixed_level, match.group().strip()[:60]

        return DEFAULT_CANDIDATE_LEVEL, "listed in document"

    def _detect_criticality(self, text: str, skill: str) -> float:
        """Detect how required a skill is from JD context."""
        text_lower = text.lower()
        skill_lower = skill.lower()

        for pattern_template, weight in CRITICALITY_SIGNALS:
            pattern = pattern_template.replace("{skill}", re.escape(skill_lower))
            if re.search(pattern, text_lower):
                return weight

        return DEFAULT_CRITICALITY

    def extract_from_resume(self, text: str) -> list[CandidateSkill]:
        """Extract skills + proficiency levels from resume text."""
        skills_found = self._find_skills_in_text(text)
        result = []
        for skill in skills_found:
            level, source = self._detect_proficiency(text, skill)
            result.append(CandidateSkill(
                name=skill,
                level=level,
                domain=SKILL_TO_DOMAIN.get(skill, "general"),
                source=source,
            ))
        return result

    def extract_from_jd(self, text: str) -> list[RequiredSkill]:
        """Extract required skills + criticality from job description text."""
        skills_found = self._find_skills_in_text(text)
        result = []
        for skill in skills_found:
            criticality = self._detect_criticality(text, skill)
            result.append(RequiredSkill(
                name=skill,
                required_level=DEFAULT_REQUIRED_LEVEL,
                criticality=criticality,
                domain=SKILL_TO_DOMAIN.get(skill, "general"),
            ))
        return result


# ---------------------------------------------------------------------------
# 6. GAP SCORER
#    YOUR ORIGINAL FORMULA:
#    urgency_score = (required_level - candidate_level) × criticality_weight
# ---------------------------------------------------------------------------

class GapScorer:
    """
    Computes the urgency score for each skill gap.
    Skills where candidate meets or exceeds requirement are dropped.
    """

    def compute_gaps(
        self,
        candidate_skills: list[CandidateSkill],
        required_skills:  list[RequiredSkill],
    ) -> list[GapSkill]:

        # Build lookup: skill name → candidate level
        candidate_map = {s.name: s for s in candidate_skills}

        gaps = []
        for req in required_skills:
            candidate = candidate_map.get(req.name)
            candidate_level = candidate.level if candidate else 0

            raw_gap = req.required_level - candidate_level

            # Skip if candidate already meets requirement
            if raw_gap <= 0:
                continue

            # YOUR FORMULA
            urgency_score = raw_gap * req.criticality

            gaps.append(GapSkill(
                name=req.name,
                domain=req.domain,
                candidate_level=candidate_level,
                required_level=req.required_level,
                gap=raw_gap,
                criticality=req.criticality,
                urgency_score=urgency_score,
                is_prerequisite=False,
            ))

        # Sort by urgency descending
        gaps.sort(key=lambda g: g.urgency_score, reverse=True)
        return gaps


# ---------------------------------------------------------------------------
# 7. DAG + TOPOLOGICAL SORT (KAHN'S ALGORITHM)
#    YOUR ORIGINAL IMPLEMENTATION
# ---------------------------------------------------------------------------

class AdaptivePathEngine:
    """
    Takes gap-scored skills and produces an ordered learning pathway
    using a prerequisite DAG and topological sort.
    """

    def _get_prerequisites(self, skill: str, visited: set) -> list[str]:
        """
        Recursively collect all prerequisites for a skill.
        Avoids infinite loops with visited set.
        """
        prereqs = PREREQUISITE_GRAPH.get(skill, [])
        result = []
        for prereq in prereqs:
            if prereq not in visited:
                visited.add(prereq)
                # Recurse to get transitive prerequisites
                result.extend(self._get_prerequisites(prereq, visited))
                result.append(prereq)
        return result

    def _build_subgraph(self, gap_skills: list[GapSkill]) -> tuple[dict, dict]:
        """
        Build a subgraph containing only:
        - The gap skills themselves
        - Any prerequisites they need (added automatically)

        Returns:
            nodes: {skill_name: GapSkill}
            edges: {skill_name: [list of skills that depend on it]}
                   (reverse of prerequisites — "who comes after me")
        """
        # Start with gap skills
        nodes: dict[str, GapSkill] = {g.name: g for g in gap_skills}
        urgency_map = {g.name: g.urgency_score for g in gap_skills}

        # Add missing prerequisites
        for gap in gap_skills:
            visited = set()
            prereqs = self._get_prerequisites(gap.name, visited)
            for prereq in prereqs:
                if prereq not in nodes:
                    # Add as a prerequisite node (not a direct gap)
                    nodes[prereq] = GapSkill(
                        name=prereq,
                        domain=SKILL_TO_DOMAIN.get(prereq, "general"),
                        candidate_level=50,
                        required_level=60,
                        gap=10,
                        criticality=1.0,
                        urgency_score=0,   # lower urgency — it's a stepping stone
                        is_prerequisite=True,
                    )

        # Build adjacency: in-degree and dependency edges
        in_degree  = defaultdict(int)
        dependents = defaultdict(list)  # skill → [skills that need it done first]

        for skill in nodes:
            prereqs = PREREQUISITE_GRAPH.get(skill, [])
            for prereq in prereqs:
                if prereq in nodes:
                    in_degree[skill] += 1
                    dependents[prereq].append(skill)

        return nodes, dict(dependents), dict(in_degree)

    def topological_sort(self, gap_skills: list[GapSkill]) -> list[GapSkill]:
        """
        Kahn's Algorithm — topological sort with urgency as tiebreaker.

        At each step:
          1. Find all skills with in-degree 0 (no remaining prerequisites)
          2. Among those, pick the one with the highest urgency score
          3. Add it to the result
          4. Remove it from the graph (decrement dependents' in-degree)
          5. Repeat

        This guarantees:
          - Prerequisites always come before the skills that need them
          - Within valid options, highest urgency comes first
        """
        nodes, dependents, in_degree = self._build_subgraph(gap_skills)

        # Initialize queue with skills that have no prerequisites
        # Use a list and sort by urgency (highest first) as our priority queue
        ready = [
            name for name in nodes
            if in_degree.get(name, 0) == 0
        ]
        ready.sort(key=lambda s: nodes[s].urgency_score, reverse=True)

        sorted_skills = []
        processed = set()

        while ready:
            # Pick the highest-urgency ready skill
            current = ready.pop(0)
            sorted_skills.append(nodes[current])
            processed.add(current)

            # Unlock dependents
            newly_ready = []
            for dependent in dependents.get(current, []):
                if dependent in processed:
                    continue
                in_degree[dependent] = in_degree.get(dependent, 1) - 1
                if in_degree[dependent] == 0:
                    newly_ready.append(dependent)

            # Insert newly ready skills in urgency order
            newly_ready.sort(key=lambda s: nodes[s].urgency_score, reverse=True)
            ready = newly_ready + ready
            ready.sort(key=lambda s: nodes[s].urgency_score, reverse=True)

        # Cycle detection — if not all nodes processed, there's a cycle
        if len(sorted_skills) != len(nodes):
            unprocessed = set(nodes.keys()) - processed
            print(f"Warning: cycle detected involving: {unprocessed}. Appending remaining.")
            for skill in unprocessed:
                sorted_skills.append(nodes[skill])

        return sorted_skills

    def _estimate_duration(self, gap: int, is_prerequisite: bool) -> int:
        """Estimate training weeks based on gap size."""
        if is_prerequisite:
            return 1
        if gap >= 80:
            return 4
        elif gap >= 60:
            return 3
        elif gap >= 40:
            return 2
        else:
            return 1

    def _assign_priority(self, urgency_score: float, is_prerequisite: bool) -> str:
        """Assign human-readable priority label."""
        if is_prerequisite:
            return "prerequisite"
        if urgency_score >= 100:
            return "critical"
        elif urgency_score >= 60:
            return "high"
        elif urgency_score >= 30:
            return "medium"
        else:
            return "low"

    def build_pathway(self, gap_skills: list[GapSkill]) -> list[PathwayModule]:
        """Convert sorted gap skills into PathwayModule objects."""
        sorted_skills = self.topological_sort(gap_skills)

        pathway = []
        for i, skill in enumerate(sorted_skills, start=1):
            pathway.append(PathwayModule(
                order=i,
                skill=skill.name,
                domain=skill.domain,
                urgency_score=round(skill.urgency_score, 1),
                candidate_level=skill.candidate_level,
                required_level=skill.required_level,
                gap=skill.gap,
                is_prerequisite=skill.is_prerequisite,
                duration_weeks=self._estimate_duration(skill.gap, skill.is_prerequisite),
                priority=self._assign_priority(skill.urgency_score, skill.is_prerequisite),
            ))

        return pathway


# ---------------------------------------------------------------------------
# 8. MAIN ENGINE — ties everything together
# ---------------------------------------------------------------------------

class AdaptiveEngine:
    """
    Main entry point.
    Call generate_pathway(resume_text, jd_text) to get the full pathway.
    """

    def __init__(self):
        self.extractor   = SkillExtractor()
        self.scorer      = GapScorer()
        self.path_engine = AdaptivePathEngine()

    def generate_pathway(
        self,
        resume_text: str,
        jd_text:     str,
        verbose:     bool = False,
    ) -> dict:

        # Step 1: Extract skills from both documents
        candidate_skills = self.extractor.extract_from_resume(resume_text)
        required_skills  = self.extractor.extract_from_jd(jd_text)

        # Step 2: Score the gaps
        gap_skills = self.scorer.compute_gaps(candidate_skills, required_skills)

        if not gap_skills:
            return {
                "pathway": [],
                "summary": "No significant skill gaps found. Candidate meets all requirements.",
                "candidate_skills": [s.__dict__ for s in candidate_skills],
                "required_skills":  [s.__dict__ for s in required_skills],
                "gap_skills":       [],
            }

        # Step 3: Topological sort → ordered pathway
        pathway = self.path_engine.build_pathway(gap_skills)

        if verbose:
            self._print_trace(candidate_skills, required_skills, gap_skills, pathway)

        total_weeks = sum(m.duration_weeks for m in pathway)
        direct_gaps = [m for m in pathway if not m.is_prerequisite]
        prereqs     = [m for m in pathway if m.is_prerequisite]

        return {
            "pathway":         [m.__dict__ for m in pathway],
            "candidate_skills":[s.__dict__ for s in candidate_skills],
            "required_skills": [s.__dict__ for s in required_skills],
            "gap_skills":      [g.__dict__ for g in gap_skills],
            "summary": {
                "total_modules":    len(pathway),
                "direct_gaps":      len(direct_gaps),
                "prerequisites_added": len(prereqs),
                "total_weeks":      total_weeks,
                "skills_already_met": len(required_skills) - len(
                    [r for r in required_skills
                     if any(g.name == r.name for g in gap_skills)]
                ),
            }
        }

    def _print_trace(self, candidate_skills, required_skills, gap_skills, pathway):
        """Reasoning trace — shows every decision the algorithm made."""
        print("\n" + "="*65)
        print("REASONING TRACE")
        print("="*65)

        print(f"\n[Step 1] Skill Extraction")
        print(f"  Resume skills found : {len(candidate_skills)}")
        for s in candidate_skills:
            print(f"    {s.name:<25} level={s.level:>3}  ({s.source})")

        print(f"\n  JD required skills  : {len(required_skills)}")
        for s in required_skills:
            print(f"    {s.name:<25} required={s.required_level}  criticality={s.criticality}")

        print(f"\n[Step 2] Gap Scoring  (formula: gap × criticality)")
        print(f"  {'Skill':<25} {'Gap':>5} {'×':>3} {'Crit':>6} {'=':>3} {'Urgency':>8}")
        print(f"  {'-'*55}")
        for g in gap_skills:
            print(f"  {g.name:<25} {g.gap:>5} {'×':>3} {g.criticality:>6.1f} {'=':>3} {g.urgency_score:>8.1f}")

        print(f"\n[Step 3] DAG + Topological Sort")
        print(f"  Final ordered pathway:")
        for m in pathway:
            tag = " [PREREQ]" if m.is_prerequisite else ""
            print(f"    {m.order}. {m.skill:<25} priority={m.priority:<12} {m.duration_weeks}wk{tag}")

        print(f"\n[Step 4] Summary")
        total = sum(m.duration_weeks for m in pathway)
        print(f"  Total modules : {len(pathway)}")
        print(f"  Total weeks   : {total}")
        print("="*65 + "\n")


# ---------------------------------------------------------------------------
# CLI — run directly to test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    SAMPLE_RESUME = """
    John Martinez - Software Engineer
    Skills: Python (intermediate), JavaScript, React, Node.js, Docker,
    PostgreSQL, Redis, AWS (basic), Git, REST APIs
    Experience: 5 years building full-stack web applications.
    Led React/Node.js projects. Basic data pipeline work with PostgreSQL.
    """

    SAMPLE_JD = """
    Machine Learning Engineer
    Required: Python (advanced, 3+ years required), PyTorch (required),
    Deep Learning (required), Scikit-learn (required), MLflow (required),
    Feature Engineering (required), Model Evaluation (required).
    Preferred: Spark, Kubernetes, Transformers (preferred).
    Must have strong statistics and linear algebra background.
    """

    engine  = AdaptiveEngine()
    results = engine.generate_pathway(SAMPLE_RESUME, SAMPLE_JD, verbose=True)

    print("\nPATHWAY MODULES")
    print("-"*65)
    for m in results["pathway"]:
        tag = " ← prerequisite" if m["is_prerequisite"] else ""
        print(
            f"  {m['order']:>2}. {m['skill']:<25} "
            f"priority={m['priority']:<12} "
            f"gap={m['gap']:>3}  "
            f"{m['duration_weeks']}wk{tag}"
        )

    s = results["summary"]
    print(f"\n  {s['total_modules']} modules · {s['total_weeks']} weeks total · "
          f"{s['skills_already_met']} skills already met (skipped)")
