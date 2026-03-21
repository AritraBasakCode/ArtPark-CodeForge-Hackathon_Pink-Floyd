export type SkillGap = {
  skill: string;
  candidate_level: number;
  required_level: number;
  gap: number;
  priority: number;
  evidence: string[];
};

export type ModuleItem = {
  module_id: string;
  title: string;
  skill_target: string;
  estimated_hours: number;
  why: string;
  prerequisites: string[];
};

export type PhaseItem = {
  phase: string;
  total_hours: number;
  modules: ModuleItem[];
};

export type PlanResult = {
  candidate_name: string;
  role_title: string;
  skill_gaps: SkillGap[];
  roadmap: PhaseItem[];
  reasoning_trace: Array<Record<string, unknown>>;
  metrics: Record<string, unknown>;
};