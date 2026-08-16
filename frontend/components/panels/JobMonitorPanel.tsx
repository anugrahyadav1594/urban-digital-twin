"use client";
import { useJobStore } from "@/stores/job-store";
import JobProgress from "@/components/ui/JobProgress";
import { Empty } from "@/components/ui/Bits";

export default function JobMonitorPanel() {
  const { jobs, clearDone } = useJobStore();
  if (jobs.length === 0) return <Empty>No jobs. Heavy operations (suitability, simulation, optimisation, AI workflows) all stream through this monitor.</Empty>;
  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted mono" style={{ fontSize: 11 }}>{jobs.filter((j) => j.state === "running").length} running · {jobs.length} total</span>
        <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={clearDone}>Clear finished</button>
      </div>
      {jobs.map((j) => <JobProgress key={j.id} job={j} />)}
    </div>
  );
}
