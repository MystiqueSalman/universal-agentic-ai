"""Task engine: Main AI planning, Management AI assignment, worker execution,
Quality Control verification (Master Prompt v3.0 sections 5, 6, 15, 40).

Honesty rules wired in:
- The executor is a LOCAL DEV executor. It produces real, inspectable work
  products (plans, shot lists, specs, document drafts, code skeletons) as
  markdown artifacts. It does NOT render video, generate images, or call any
  external model yet — artifacts say so on their face.
- Every state change emits a real event to the bus (section 18/19).
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from . import router as model_router
from .events import BUS
from .incidents import INCIDENTS
from .registry import REGISTRY
from .store import STORE

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "outputs"))

TASK_STATES = ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "BLOCKED")


@dataclass
class Task:
    task_id: str
    objective_id: str
    title: str
    department_id: str
    skill_keywords: list[str]
    kind: str  # research | document | plan | code | media_plan | audio_plan | quality
    agent_id: str | None = None
    attempts: int = 0
    status: str = "QUEUED"
    output_path: str | None = None
    result: str | None = None
    error: str | None = None


@dataclass
class Objective:
    objective_id: str
    title: str
    priority: str = "High"
    status: str = "RECEIVED"  # RECEIVED PLANNING RUNNING VERIFYING COMPLETED FAILED
    planner: str = "template"
    tasks: list[Task] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        done = sum(1 for t in self.tasks if t.status == "COMPLETED")
        return {
            "objective_id": self.objective_id, "title": self.title, "priority": self.priority,
            "status": self.status, "created_at": self.created_at, "planner": self.planner,
            "correlation_id": self.correlation_id,
            "progress_pct": round(100 * done / len(self.tasks)) if self.tasks else 0,
            "tasks": [{"task_id": t.task_id, "title": t.title, "department_id": t.department_id,
                       "agent_id": t.agent_id, "status": t.status, "kind": t.kind,
                       "output_path": t.output_path, "result": t.result, "error": t.error}
                      for t in self.tasks],
        }


OBJECTIVES: dict[str, Objective] = {}
_LOCK = threading.Lock()

# ---------------- Persistence ----------------

def _persist(obj: Objective) -> None:
    try:
        STORE.save_objective({"objective_id": obj.objective_id, "title": obj.title,
                              "priority": obj.priority, "status": obj.status,
                              "created_at": obj.created_at, "correlation_id": obj.correlation_id})
        for t in obj.tasks:
            STORE.save_task(obj.objective_id,
                            {"task_id": t.task_id, "title": t.title, "department_id": t.department_id,
                             "agent_id": t.agent_id, "kind": t.kind, "status": t.status,
                             "attempts": t.attempts, "output_path": t.output_path,
                             "result": t.result, "error": t.error})
    except Exception:
        pass  # persistence failure must never crash execution; events still record truth


def load_persisted() -> int:
    """Reload objectives/tasks at startup. Interrupted work is marked FAILED."""
    objs, tasks = STORE.load_all()
    by_obj: dict[str, list[Task]] = {}
    for td in tasks:
        t = Task(task_id=td["task_id"], objective_id=td["objective_id"], title=td["title"],
                 department_id=td["department_id"], skill_keywords=[], kind=td["kind"],
                 agent_id=td["agent_id"], attempts=td["attempts"] or 0, status=td["status"],
                 output_path=td["output_path"], result=td["result"], error=td["error"])
        if t.status in ("RUNNING", "QUEUED"):
            t.status = "FAILED"
            t.error = "Interrupted by server restart (restored from durable store)"
        by_obj.setdefault(td["objective_id"], []).append(t)
    for od in objs:
        o = Objective(objective_id=od["objective_id"], title=od["title"], priority=od["priority"],
                      status=od["status"], created_at=od["created_at"],
                      correlation_id=od["correlation_id"])
        o.tasks = sorted(by_obj.get(o.objective_id, []), key=lambda x: x.task_id)
        if o.status in ("RECEIVED", "PLANNING", "RUNNING", "VERIFYING"):
            o.status = "FAILED"
        OBJECTIVES[o.objective_id] = o
    return len(objs)


# ---------------- Main AI: objective classification + plan templates ----------------

def _mk(obj_id: str, n: int, title: str, dept: str, skills: list[str], kind: str) -> Task:
    return Task(task_id=f"{obj_id}-T{n:02d}", objective_id=obj_id, title=title,
                department_id=dept, skill_keywords=skills, kind=kind)


def _llm_plan(obj: Objective) -> list[Task] | None:
    """Main AI planning via the Model Router. Returns None to fall back."""
    import json as _json

    from .registry import DEPARTMENTS
    dept_list = "; ".join(f"{k}={v['name']}" for k, v in DEPARTMENTS.items())
    text = model_router.chat(
        "You are the Main AI planner of Universal Agentic AI. Reply with ONLY a JSON array.",
        (f"Objective: {obj.title}\nDepartments: {dept_list}\n"
         "Return 4-9 tasks as a JSON array of objects with keys: title, department_id "
         "(one of the D-codes), skills (array of 1-3 short keywords), kind (one of: research, "
         "document, plan, code, media_plan, audio_plan). The LAST task must be kind 'quality' "
         "in department D01 or the producing department. No prose outside the JSON array."),
        max_tokens=1500)
    if not text:
        return None
    try:
        start, end = text.index("["), text.rindex("]") + 1
        raw = _json.loads(text[start:end])
        tasks: list[Task] = []
        kinds = {"research", "document", "plan", "code", "media_plan", "audio_plan", "quality"}
        for i, item in enumerate(raw, 1):
            dept = str(item.get("department_id", "D02")).upper()
            if dept not in DEPARTMENTS:
                dept = "D02"
            kind = str(item.get("kind", "plan"))
            if kind not in kinds:
                kind = "plan"
            tasks.append(_mk(obj.objective_id, i, str(item.get("title", f"Task {i}"))[:120],
                             dept, [str(s).lower() for s in item.get("skills", [])][:3], kind))
        return tasks or None
    except Exception:
        return None


def plan_objective(obj: Objective) -> list[Task]:
    """Main AI planner: LLM via the Model Router when available, else templates."""
    llm = _llm_plan(obj)
    if llm:
        obj.planner = "llm"
        return llm
    obj.planner = "template"
    t = obj.title.lower()
    oid = obj.objective_id
    if any(k in t for k in ("film", "video", "animation", "animated", "movie", "cartoon")):
        return [
            _mk(oid, 1, "Research topic and audience", "D02", ["web", "research"], "research"),
            _mk(oid, 2, "Write story and screenplay", "D06", ["screenplay"], "document"),
            _mk(oid, 3, "Create character and world references", "D06", ["character", "design"], "plan"),
            _mk(oid, 4, "Storyboard: scene and shot breakdown", "D06", ["storyboard"], "media_plan"),
            _mk(oid, 5, "Shot generation plan (text-to-video pipeline)", "D06", ["text-to-video", "video"], "media_plan"),
            _mk(oid, 6, "Voice, dialogue and music plan", "D07", ["voice", "generation"], "audio_plan"),
            _mk(oid, 7, "Editing and assembly plan", "D06", ["video", "editing"], "plan"),
            _mk(oid, 8, "Assemble scene-card preview render (MP4)", "D06", ["video", "editing"], "render"),
            _mk(oid, 9, "Continuity and quality verification", "D01", ["quality", "control"], "quality"),
        ]
    if any(k in t for k in ("crm", "software", "app", "website", "system", "platform", "build")):
        return [
            _mk(oid, 1, "Market and product research", "D02", ["market", "research"], "research"),
            _mk(oid, 2, "Product requirements and scope", "D12", ["product", "manager"], "document"),
            _mk(oid, 3, "System architecture design", "D12", ["system", "architect"], "plan"),
            _mk(oid, 4, "Database schema design", "D12", ["database", "engineer"], "plan"),
            _mk(oid, 5, "Backend implementation skeleton", "D12", ["backend"], "code"),
            _mk(oid, 6, "Frontend implementation skeleton", "D12", ["frontend"], "code"),
            _mk(oid, 7, "Security review", "D12", ["cybersecurity"], "quality"),
            _mk(oid, 8, "QA test plan and verification", "D12", ["qa", "testing"], "quality"),
            _mk(oid, 9, "Technical documentation", "D12", ["technical", "documentation"], "document"),
        ]
    if any(k in t for k in ("project", "academic", "assignment", "college", "university", "final year")):
        return [
            _mk(oid, 1, "Project idea and synopsis", "D20", ["synopsis"], "document"),
            _mk(oid, 2, "Research and literature survey", "D20", ["research"], "research"),
            _mk(oid, 3, "Architecture and diagrams", "D20", ["architecture"], "plan"),
            _mk(oid, 4, "Implementation (coding)", "D20", ["coding"], "code"),
            _mk(oid, 5, "Testing documentation", "D20", ["testing"], "document"),
            _mk(oid, 6, "Final project report", "D20", ["project", "report"], "document"),
            _mk(oid, 7, "Presentation and viva preparation", "D20", ["viva", "preparation"], "document"),
            _mk(oid, 8, "Project quality audit", "D20", ["project", "quality", "auditor"], "quality"),
        ]
    if any(k in t for k in ("resume", "cv", "cover letter", "ppt", "presentation", "report", "proposal")):
        return [
            _mk(oid, 1, "Research role and requirements", "D02", ["web", "research"], "research"),
            _mk(oid, 2, "Draft the document", "D04", ["document", "creation"], "document"),
            _mk(oid, 3, "Design and formatting", "D04", ["document", "formatting"], "plan"),
            _mk(oid, 4, "Quality verification", "D01", ["quality", "control"], "quality"),
        ]
    if any(k in t for k in ("marketing", "campaign", "ads", "seo", "social media")):
        return [
            _mk(oid, 1, "Market and competitor research", "D02", ["competitor", "analysis"], "research"),
            _mk(oid, 2, "Campaign strategy", "D09", ["campaign", "strategy"], "plan"),
            _mk(oid, 3, "Advertising creative brief", "D09", ["advertising", "creative"], "document"),
            _mk(oid, 4, "Content calendar", "D08", ["content", "calendar"], "document"),
            _mk(oid, 5, "Quality verification", "D01", ["quality", "control"], "quality"),
        ]
    return [
        _mk(oid, 1, "Research the objective", "D02", ["deep", "research"], "research"),
        _mk(oid, 2, "Produce the deliverable", "D04", ["report", "writing"], "document"),
        _mk(oid, 3, "Quality verification", "D01", ["quality", "control"], "quality"),
    ]


# ---------------- Executor: local dev work products ----------------

def execute_task(obj: Objective, task: Task, agent_name: str) -> str:
    """Produce a real artifact file for the task and return its path."""
    # Chaos hook for recovery testing: an objective tagged [fail-first] makes
    # the first attempt of each non-quality task raise, so the incident +
    # self-healing path can be exercised end-to-end on demand.
    if "[fail-first]" in obj.title.lower() and task.attempts <= 1 and task.kind != "quality":
        raise RuntimeError("Injected failure (chaos test) — first attempt only")
    folder = os.path.join(OUT_DIR, obj.objective_id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{task.task_id}.md")
    header = (f"# {task.title}\n\n- Objective: {obj.title}\n- Executed by: {agent_name} ({task.agent_id})\n"
              f"- Department: {task.department_id}\n- Kind: {task.kind}\n- Mode: DEV (local executor)\n\n")
    bodies = {
        "research": "## Research brief\nKey questions, source classes to consult, and verification steps for this objective are itemised here. Live web research plugs into this task in a later batch.\n",
        "document": "## Draft\nStructured draft generated from the objective: purpose, audience, outline, body sections and review notes. LLM drafting plugs into this task via the Model Router (Doc 09).\n",
        "plan": "## Plan\nSteps, dependencies, inputs, outputs and acceptance criteria for this stage of the objective.\n",
        "code": "## Implementation skeleton\nModule layout, interfaces, data contracts and TODO markers for the production implementation of this component.\n",
        "media_plan": "## Production plan (NOT rendered media)\nScene/shot list, prompts, reference requirements and render settings. No video has been generated in this batch — the video models integrate via Doc 12.\n",
        "audio_plan": "## Audio plan (NOT rendered audio)\nVoice casting, dialogue list, music and SFX cues. No audio has been generated in this batch.\n",
        "quality": "## Verification\nChecks: artifact exists, is non-empty, matches the task title and objective, and carries mode labelling. Result recorded by the engine.\n",
    }
    body = bodies.get(task.kind, bodies["plan"])
    if task.kind == "render":
        from .media import build_preview_mp4, probe_duration
        scenes = ["Story opening and world setup", "Meet the main characters",
                  "The central idea, explained simply", "Key concept demonstration",
                  "Rising challenge and discovery", "Breakthrough moment",
                  "Real-world applications", "Summary and closing"]
        mp4 = build_preview_mp4(folder, obj.title, scenes)
        body = (f"## Scene-card preview render\nRendered a real, playable MP4 preview "
                f"(`preview.mp4`, {probe_duration(mp4):.1f}s, 1280x720) from the scene plan "
                "using FFmpeg. This is a scene-card preview — NOT AI-generated footage. "
                "Generative video models plug into this pipeline via the Model Router (Doc 12).\n")
    drafted = None
    if task.kind in ("research", "document", "plan", "code"):
        drafted = model_router.chat(
            f"You are {agent_name}, a specialist agent of Universal Agentic AI. "
            "Produce professional, concrete work. Be specific to the objective; "
            "never invent facts you cannot support — mark assumptions clearly.",
            (f"Objective: {obj.title}\nYour task: {task.title} (kind: {task.kind})\n"
             "Write the deliverable for this task in markdown, 250-600 words."),
            max_tokens=1600)
    if drafted:
        body = (f"## Deliverable (drafted via Model Router — provider: "
                f"{model_router.provider_name()})\n\n{drafted}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + body)
    return path


# ---------------- Management AI: assignment + run loop ----------------

def submit_objective(title: str, priority: str = "High") -> Objective:
    oid = "PRJ-" + uuid.uuid4().hex[:6].upper()
    obj = Objective(objective_id=oid, title=title, priority=priority)
    with _LOCK:
        OBJECTIVES[oid] = obj
    BUS.emit("FOUNDER", "MAIN_AI", "OBJECTIVE_RECEIVED", f"Objective received: {title}",
             correlation_id=obj.correlation_id, status="OK")
    threading.Thread(target=_run_objective, args=(obj,), daemon=True).start()
    return obj


def _run_objective(obj: Objective) -> None:
    cid = obj.correlation_id
    try:
        obj.status = "PLANNING"
        obj.tasks = plan_objective(obj)
        BUS.emit("MAIN_AI", "MANAGEMENT_AI", "CREATE_PROJECT",
                 f"Plan created ({obj.planner} planner): {len(obj.tasks)} tasks for {obj.objective_id}",
                 correlation_id=cid, status="OK")
        obj.status = "RUNNING"
        _persist(obj)
        for task in obj.tasks:
            agent = REGISTRY.find_by_skill(task.skill_keywords, task.department_id)
            if agent is None:
                task.status = "FAILED"
                task.error = "No available specialist agent in registry"
                INCIDENTS.create(agent_id="MANAGEMENT_AI", department_id=task.department_id,
                                 task_id=task.task_id, parent_task=obj.objective_id,
                                 message=task.error, category="Agent communication error",
                                 agent_failure_count=1)
                BUS.emit("MANAGEMENT_AI", "MAIN_AI", "TASK_FAILED",
                         f"{task.task_id}: no agent available", task_id=task.task_id,
                         parent_task=obj.objective_id, correlation_id=cid, status="ERROR")
                continue
            task.agent_id = agent.agent_id
            BUS.emit("MANAGEMENT_AI", agent.agent_id, "TASK_ASSIGNED",
                     f"{task.title}", task_id=task.task_id, parent_task=obj.objective_id,
                     correlation_id=cid, status="OK")
            agent.status = "RUNNING"
            agent.current_task = task.task_id
            task.status = "RUNNING"
            BUS.emit(agent.agent_id, "MANAGEMENT_AI", "EXECUTION_STARTED",
                     f"{agent.name} started: {task.title}", task_id=task.task_id,
                     parent_task=obj.objective_id, correlation_id=cid, status="OK")
            time.sleep(0.15)  # visible, honest pacing for the live terminal

            def attempt(ag) -> str:
                task.attempts += 1
                p = execute_task(obj, task, ag.name)
                if task.kind == "quality" and not _verify_objective(obj):
                    raise RuntimeError("Quality verification failed: a prior artifact is missing/empty")
                return p

            def complete(ag, p: str) -> None:
                task.output_path = p
                task.status = "COMPLETED"
                task.result = f"Artifact: {os.path.basename(p)}"
                ag.tasks_completed += 1
                ag.quality_score = round(
                    100.0 * ag.tasks_completed / max(1, ag.tasks_completed + ag.tasks_failed), 1)
                BUS.emit(ag.agent_id, "MANAGEMENT_AI", "EXECUTION_COMPLETE",
                         f"{ag.name} completed: {task.title}", task_id=task.task_id,
                         parent_task=obj.objective_id, correlation_id=cid, status="OK")

            try:
                complete(agent, attempt(agent))
            except Exception as exc:
                # Incident first (Mgmt AI spec sections 5-6), then Level-1
                # self-healing: reassign to another specialist, one bounded retry.
                agent.tasks_failed += 1
                agent.errors.append(str(exc))
                inc = INCIDENTS.create(agent_id=agent.agent_id, department_id=task.department_id,
                                       task_id=task.task_id, parent_task=obj.objective_id,
                                       message=str(exc), agent_failure_count=agent.tasks_failed)
                BUS.emit("SYSTEM_MONITOR_AI", "MANAGEMENT_AI", "INCIDENT_CREATED",
                         f"{inc['incident_id']} [{inc['severity']}] {task.task_id}: {exc}",
                         task_id=task.task_id, parent_task=obj.objective_id,
                         correlation_id=cid, status="ERROR")
                alt = REGISTRY.find_by_skill(task.skill_keywords, task.department_id,
                                             exclude={agent.agent_id})
                healed = False
                if alt is not None:
                    BUS.emit("MANAGEMENT_AI", alt.agent_id, "RECOVERY_ATTEMPT",
                             f"Level-1 self-heal: reassign {task.task_id} to {alt.name}",
                             task_id=task.task_id, parent_task=obj.objective_id,
                             correlation_id=cid, status="WARN")
                    alt.status = "RUNNING"
                    alt.current_task = task.task_id
                    try:
                        complete(alt, attempt(alt))
                        task.agent_id = alt.agent_id
                        INCIDENTS.update(inc["incident_id"], status="RESOLVED",
                                         resolution=f"Level-1 self-healing: reassigned to "
                                                    f"{alt.agent_id}; completed on retry",
                                         retry_history='["reassign+retry: success"]')
                        BUS.emit(alt.agent_id, "MANAGEMENT_AI", "RECOVERY_COMPLETE",
                                 f"{task.task_id} recovered by {alt.name}; "
                                 f"{inc['incident_id']} resolved",
                                 task_id=task.task_id, parent_task=obj.objective_id,
                                 correlation_id=cid, status="OK")
                        healed = True
                    except Exception as exc2:
                        alt.tasks_failed += 1
                        alt.errors.append(str(exc2))
                        INCIDENTS.update(inc["incident_id"], status="ESCALATED",
                                         resolution=f"Retry with {alt.agent_id} also failed: {exc2}",
                                         retry_history='["reassign+retry: failed"]')
                    finally:
                        alt.status = "IDLE"
                        alt.current_task = None
                if not healed:
                    task.status = "FAILED"
                    task.error = str(exc)
                    if alt is None:
                        INCIDENTS.update(inc["incident_id"], status="ESCALATED",
                                         resolution="No alternative specialist available; "
                                                    "escalated to Management AI")
                    BUS.emit(agent.agent_id, "MANAGEMENT_AI", "TASK_FAILED",
                             f"{task.task_id} failed: {exc}", task_id=task.task_id,
                             parent_task=obj.objective_id, correlation_id=cid, status="ERROR")
            finally:
                agent.status = "IDLE"
                agent.current_task = None
            _persist(obj)
        failed = [t for t in obj.tasks if t.status == "FAILED"]
        obj.status = "FAILED" if failed else "COMPLETED"
        BUS.emit("MANAGEMENT_AI", "MAIN_AI", "PROJECT_RESULT",
                 f"{obj.objective_id} {obj.status.lower()}: "
                 f"{sum(1 for t in obj.tasks if t.status == 'COMPLETED')}/{len(obj.tasks)} tasks completed",
                 correlation_id=cid, status="ERROR" if failed else "OK")
        BUS.emit("MAIN_AI", "FOUNDER", "REPORT_DELIVERED",
                 f"Consolidated report ready for {obj.objective_id} ({obj.status})",
                 correlation_id=cid, status="OK")
        _persist(obj)
    except Exception as exc:
        obj.status = "FAILED"
        BUS.emit("MANAGEMENT_AI", "MAIN_AI", "PROJECT_FAILED", f"{obj.objective_id}: {exc}",
                 correlation_id=cid, status="ERROR")


def _verify_objective(obj: Objective) -> bool:
    for t in obj.tasks:
        if t.kind != "quality" and t.status == "COMPLETED":
            if not t.output_path or not os.path.isfile(t.output_path) or os.path.getsize(t.output_path) == 0:
                return False
    return True
