import type { PlanResult } from "./types";

const API_BASE = "http://localhost:8000";

export async function generatePlan(resume: File, jobDescription: File): Promise<PlanResult> {
  const form = new FormData();
  form.append("resume", resume);
  form.append("job_description", jobDescription);

  const res = await fetch(`${API_BASE}/api/generate-plan`, {
    method: "POST",
    body: form
  });

  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || "Failed to generate plan");
  }

  return res.json();
}