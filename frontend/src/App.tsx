import { useState } from "react";
import { generatePlan } from "./api";
import type { PlanResult } from "./types";
import "./styles.css";

export default function App() {
  const [resume, setResume] = useState<File | null>(null);
  const [jd, setJd] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [error, setError] = useState("");

  const onSubmit = async () => {
    if (!resume || !jd) return setError("Please upload both Resume and Job Description files.");
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const data = await generatePlan(resume, jd);
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>AI-Adaptive Onboarding Engine</h1>
      <p className="subtitle">Upload Resume + JD to generate personalized training roadmap.</p>

      <div className="card">
        <div className="row">
          <div>
            <label>Resume (txt for demo)</label>
            <input type="file" accept=".txt,.md" onChange={(e) => setResume(e.target.files?.[0] || null)} />
          </div>
          <div>
            <label>Job Description (txt for demo)</label>
            <input type="file" accept=".txt,.md" onChange={(e) => setJd(e.target.files?.[0] || null)} />
          </div>
        </div>
        <button onClick={onSubmit} disabled={loading}>
          {loading ? "Generating..." : "Generate Adaptive Plan"}
        </button>
        {error && <p className="error">{error}</p>}
      </div>

      {result && (
        <>
          <div className="card">
            <h2>Candidate Summary</h2>
            <p><b>Name:</b> {result.candidate_name}</p>
            <p><b>Target Role:</b> {result.role_title}</p>
            <pre>{JSON.stringify(result.metrics, null, 2)}</pre>
          </div>

          <div className="card">
            <h2>Skill Gap Analysis</h2>
            <table>
              <thead>
                <tr>
                  <th>Skill</th><th>Candidate</th><th>Required</th><th>Gap</th><th>Priority</th>
                </tr>
              </thead>
              <tbody>
                {result.skill_gaps.map((s) => (
                  <tr key={s.skill}>
                    <td>{s.skill}</td>
                    <td>{s.candidate_level}</td>
                    <td>{s.required_level}</td>
                    <td>{s.gap}</td>
                    <td>{s.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Adaptive Roadmap</h2>
            {result.roadmap.map((phase) => (
              <div key={phase.phase} className="phase">
                <h3>{phase.phase} ({phase.total_hours}h)</h3>
                <ul>
                  {phase.modules.map((m) => (
                    <li key={m.module_id}>
                      <b>{m.module_id} - {m.title}</b> [{m.skill_target}] ({m.estimated_hours}h)
                      <div className="muted">Why: {m.why}</div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>Reasoning Trace</h2>
            <pre>{JSON.stringify(result.reasoning_trace, null, 2)}</pre>
          </div>
        </>
      )}
    </div>
  );
}