"""Agent Registry — Universal Agentic AI (Master Prompt v3.0, sections 8-9).

Every specialist named in section 9 is a registered agent record:
id, name, department, manager, skills, model config, permissions,
I/O schema, benchmarks, version, execution + error history, quality score.
Agents are configurations on shared runtimes — NOT separate foundation models.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

DEPARTMENTS: dict[str, dict] = {
    "D01": {"name": "Command and Control Intelligence", "specialists": [
        "Main AI", "Management AI", "Task Planning AI", "Task Scheduling AI", "Agent Selection AI",
        "Agent Coordination AI", "Agent Registry AI", "Agent Creation AI", "Memory Manager AI",
        "Resource Manager AI", "Agent Performance AI", "Security Guardian AI", "Quality Control AI",
        "System Recovery AI", "Decision Support AI"]},
    "D02": {"name": "Research and Intelligence", "specialists": [
        "Web Research AI", "Deep Research AI", "Academic Research AI", "Scientific Research AI",
        "Market Research AI", "Competitor Analysis AI", "Fact Checker AI", "Patent Research AI",
        "Product Research AI", "Trend Detection AI", "Opportunity Discovery AI", "Data Verification AI",
        "Research Reporting AI"]},
    "D03": {"name": "Personal Intelligence", "specialists": [
        "Personal Assistant AI", "Profile Creation AI", "Personal Branding AI", "Career Advisor AI",
        "LinkedIn Profile AI", "Portfolio AI", "Email Assistant AI", "Calendar AI", "Travel Planner AI",
        "Meeting Assistant AI", "Interview Preparation AI", "Job Discovery AI", "Job Application AI",
        "Personal Knowledge AI"]},
    "D04": {"name": "Professional Documents and Presentations", "specialists": [
        "Resume Builder AI", "Cover Letter AI", "PPT Creation AI", "Business Proposal AI",
        "Report Writing AI", "Document Creation AI", "Spreadsheet AI", "Professional Letter AI",
        "Presentation Design AI", "Document Formatting AI", "Citation AI", "Business Plan AI",
        "Portfolio Document AI"]},
    "D05": {"name": "Creative Design Intelligence", "specialists": [
        "Image Generation AI", "Image Editing AI", "Image Restoration AI", "Graphic Design AI",
        "Logo Design AI", "Brand Identity AI", "Character Design AI", "Photo Editing AI",
        "Illustration AI", "Advertisement Design AI", "Product Design AI", "UI/UX Design AI",
        "Infographic AI", "Creative Direction AI"]},
    "D06": {"name": "Film, Animation and Cinematic Intelligence", "specialists": [
        "Film Director AI", "Screenplay AI", "Story Development AI", "Dialogue AI", "Film Producer AI",
        "Assistant Director AI", "Casting AI", "Storyboard AI", "Cinematography AI", "Camera Movement AI",
        "Character Design AI", "Digital Human AI", "2D Animation AI", "3D Animation AI", "Cartoon AI",
        "Motion Capture AI", "Facial Animation AI", "Lip-Sync AI", "Text-to-Video AI", "Image-to-Video AI",
        "Photo-to-Video AI", "Video Editing AI", "Scene Continuity AI", "Film Colour Grading AI",
        "Compositing AI", "Video Quality AI"]},
    "D07": {"name": "Audio and Voice Intelligence", "specialists": [
        "Voice Generation AI", "Voice Recognition AI", "Speech-to-Text AI", "Text-to-Speech AI",
        "Voice Dubbing AI", "Translation AI", "Music Creation AI", "Sound Effects AI", "Audio Editing AI",
        "Audio Restoration AI", "Consent-Based Voice Cloning AI", "Dialogue Quality AI"]},
    "D08": {"name": "Social Media Intelligence", "specialists": [
        "Social Media Manager AI", "Instagram AI", "Facebook AI", "YouTube AI", "LinkedIn AI",
        "TikTok AI", "X/Twitter AI", "Content Calendar AI", "Community Management AI",
        "Reputation Management AI", "Social Analytics AI", "Social Publishing AI"]},
    "D09": {"name": "Marketing and Advertising Intelligence", "specialists": [
        "Advertising Director AI", "Google Ads AI", "Meta Ads AI", "YouTube Ads AI", "LinkedIn Ads AI",
        "TikTok Ads AI", "SEO AI", "Campaign Strategy AI", "Advertising Creative AI",
        "Budget Optimisation AI", "A/B Testing AI", "Conversion Optimisation AI", "Marketing Analytics AI",
        "Landing Page AI", "Marketing Automation AI"]},
    "D10": {"name": "Lead Generation and Sales Intelligence", "specialists": [
        "Lead Generation AI", "Prospect Research AI", "Lead Enrichment AI", "Lead Qualification AI",
        "Email Outreach AI", "WhatsApp Business AI", "Sales Assistant AI", "Appointment Setter AI",
        "Follow-up AI", "Sales Proposal AI", "Sales Negotiation Assistant AI", "Sales Analytics AI",
        "Customer Acquisition AI"]},
    "D11": {"name": "CRM and Customer Experience", "specialists": [
        "CRM Manager AI", "CRM Data AI", "Pipeline Management AI", "Customer Support AI",
        "Customer Onboarding AI", "Ticket Management AI", "Customer Success AI", "Customer Retention AI",
        "Customer Feedback AI", "Knowledge Base AI", "Customer Analytics AI"]},
    "D12": {"name": "Software Development and Technology", "specialists": [
        "Product Manager AI", "System Architect AI", "Python Developer AI", "Java Developer AI",
        "C/C++ Developer AI", "JavaScript Developer AI", "Frontend Developer AI", "Backend Developer AI",
        "Full Stack Developer AI", "Mobile Developer AI", "API Integration AI", "Database Engineer AI",
        "UI/UX Designer AI", "QA Testing AI", "Debugging AI", "DevOps AI", "Cloud Engineer AI",
        "Cybersecurity AI", "Automation Engineer AI", "Technical Documentation AI"]},
    "D13": {"name": "Data and Analytics Intelligence", "specialists": [
        "Data Analyst AI", "Data Engineer AI", "Business Intelligence AI", "Dashboard AI",
        "Predictive Analytics AI", "Machine Learning AI", "Deep Learning AI", "Statistical Analysis AI",
        "Data Quality AI", "Data Visualisation AI", "Financial Data Analyst AI"]},
    "D14": {"name": "Finance and Accounting Intelligence", "specialists": [
        "Accounting AI", "Bookkeeping AI", "Invoice AI", "Expense Management AI", "Budget Planner AI",
        "Cash Flow AI", "Financial Analysis AI", "Payroll Assistant AI", "Tax Documentation AI",
        "Financial Forecasting AI", "Risk Analysis AI"]},
    "D15": {"name": "Human Resources Intelligence", "specialists": [
        "Recruitment AI", "Resume Screening AI", "Job Description AI", "Interview Scheduling AI",
        "Interview Assistant AI", "Employee Onboarding AI", "Training Manager AI", "HR Documentation AI",
        "Workforce Planning AI", "Employee Support AI"]},
    "D16": {"name": "Legal and Compliance Intelligence", "specialists": [
        "Legal Research AI", "Contract Analysis AI", "Agreement Drafting AI", "Corporate Compliance AI",
        "Intellectual Property AI", "Privacy Compliance AI", "Regulatory Research AI",
        "Legal Documentation AI", "Compliance Monitoring AI"]},
    "D17": {"name": "Operations and Project Management", "specialists": [
        "Project Manager AI", "Operations Manager AI", "Workflow Manager AI", "Task Management AI",
        "SOP Creation AI", "Vendor Management AI", "Procurement AI", "Inventory AI", "Logistics AI",
        "Supply Chain AI", "Quality Management AI", "Meeting Coordinator AI"]},
    "D18": {"name": "Education and Learning Intelligence", "specialists": [
        "Curriculum Designer AI", "Course Creator AI", "Lesson Planner AI", "AI Tutor",
        "Quiz Generator AI", "Student Support AI", "Assignment Evaluator AI", "Learning Progress AI",
        "LMS Manager AI", "Examination Preparation AI", "Educational Research AI"]},
    "D19": {"name": "Industry Intelligence", "specialists": [
        "Education Industry AI", "Real Estate Industry AI", "Healthcare Admin Industry AI",
        "Hospitality Industry AI", "Retail Industry AI", "E-commerce Industry AI",
        "Manufacturing Industry AI", "Construction Industry AI", "Agriculture Industry AI",
        "Automotive Industry AI", "Aerospace Industry AI", "Engineering Industry AI",
        "Architecture Industry AI", "Banking Operations Industry AI", "Insurance Industry AI",
        "Government Admin Industry AI", "NGO Industry AI", "Travel Industry AI",
        "Marketing Agency Industry AI", "Law Firm Industry AI", "Accounting Firm Industry AI",
        "Scientific Research Industry AI", "Energy Industry AI", "Environment Industry AI",
        "Fashion Industry AI", "Robotics Industry AI", "Logistics Industry AI",
        "Transportation Industry AI", "Beauty and Salon Industry AI", "Corporate Office Industry AI"]},
    "D20": {"name": "Academic and Project Intelligence", "specialists": [
        "Academic Project Manager AI", "Project Idea AI", "Project Guide AI", "Synopsis AI",
        "Research AI", "Documentation AI", "Architecture AI", "Diagram AI", "Coding AI", "Database AI",
        "Testing AI", "Debugging AI", "Project Report AI", "PPT AI", "Viva Preparation AI",
        "AI Project Mentor", "Project Quality Auditor AI"]},
}

STOPWORDS = {"ai", "and", "the", "for"}


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def skills_for(name: str) -> list[str]:
    words = [w.lower() for w in re.split(r"[^A-Za-z0-9+#]+", name) if w and w.lower() not in STOPWORDS]
    return sorted(set(words))


@dataclass
class Agent:
    agent_id: str
    name: str
    department_id: str
    department: str
    manager: str
    role: str  # MAIN | MANAGEMENT | DEPARTMENT_MANAGER | SPECIALIST
    skills: list[str]
    model_provider: str = "router-default"
    model_id: str = "auto"
    status: str = "IDLE"  # IDLE RUNNING WAITING BLOCKED FAILED OFFLINE QUARANTINED DISABLED PAUSED
    version: str = "0.1.0"
    tasks_completed: int = 0
    tasks_failed: int = 0
    quality_score: float = 0.0
    current_task: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id, "name": self.name, "department_id": self.department_id,
            "department": self.department, "manager": self.manager, "role": self.role,
            "skills": self.skills, "model_provider": self.model_provider, "model_id": self.model_id,
            "status": self.status, "version": self.version,
            "tasks_completed": self.tasks_completed, "tasks_failed": self.tasks_failed,
            "quality_score": self.quality_score, "current_task": self.current_task,
            "success_rate": (round(100.0 * self.tasks_completed / (self.tasks_completed + self.tasks_failed), 1)
                             if (self.tasks_completed + self.tasks_failed) else None),
        }


class Registry:
    """Single source of truth for departments and agents (Doc 07 precursor)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.agents: dict[str, Agent] = {}
        self._seed()

    def _seed(self) -> None:
        # Level 2 / 3 — the two central intelligences live in D01 but outrank managers.
        for name, role, mgr in [
            ("Main AI", "MAIN", "FOUNDER"),
            ("Management AI", "MANAGEMENT", "MAIN_AI"),
        ]:
            aid = slug(name)
            self.agents[aid] = Agent(aid, name, "D01", DEPARTMENTS["D01"]["name"], mgr, role,
                                     skills_for(name) + (["orchestration", "strategy"] if role == "MAIN"
                                                         else ["planning", "assignment", "coordination"]))
        # Management AI Technical Operations hierarchy (Management AI Master
        # Prompt v1.0, section 3): ops specialists reporting directly to
        # Management AI. Roles that already exist elsewhere in the catalogue
        # (DevOps AI, Debugging AI, QA Testing AI, System Recovery AI,
        # Database Engineer AI, Cloud Engineer AI) are NOT duplicated.
        for name in [
            "System Monitor AI", "Diagnostic AI", "Root Cause Analysis AI", "Code Repair AI",
            "Backend Engineering AI", "Frontend Engineering AI", "API Troubleshooting AI",
            "Agent Communication Repair AI", "Memory System Repair AI", "Regression Testing AI",
            "Cybersecurity Auditor AI", "GPU Infrastructure AI", "Performance Optimisation AI",
            "Disaster Recovery AI", "Independent Verification AI",
        ]:
            aid = slug(name)
            self.agents[aid] = Agent(aid, name, "D01", DEPARTMENTS["D01"]["name"], "MANAGEMENT_AI",
                                     "SPECIALIST", skills_for(name) + ["operations", "recovery"])
        for dept_id, dept in DEPARTMENTS.items():
            mgr_id = slug(f"{dept['name']} Manager")
            if dept_id == "D01":
                mgr_name, mgr_role = "Management AI", "MANAGEMENT"
            else:
                mgr_name = f"{dept['name']} Manager"
                self.agents[mgr_id] = Agent(mgr_id, mgr_name, dept_id, dept["name"], "MANAGEMENT_AI",
                                            "DEPARTMENT_MANAGER", skills_for(dept["name"]) + ["management"])
            for spec in dept["specialists"]:
                if spec in ("Main AI", "Management AI"):
                    continue
                aid = slug(spec)
                if aid in self.agents:  # a few names repeat across departments in the prompt
                    aid = f"{dept_id}_{aid}"
                manager = "MANAGEMENT_AI" if dept_id == "D01" else mgr_id
                self.agents[aid] = Agent(aid, spec, dept_id, dept["name"], manager, "SPECIALIST",
                                         skills_for(spec))

    def list_departments(self) -> list[dict]:
        out = []
        for dept_id, dept in DEPARTMENTS.items():
            count = sum(1 for a in self.agents.values() if a.department_id == dept_id)
            out.append({"department_id": dept_id, "name": dept["name"], "agent_count": count})
        return out

    def list_agents(self, department_id: str | None = None) -> list[Agent]:
        agents = list(self.agents.values())
        if department_id:
            agents = [a for a in agents if a.department_id == department_id]
        return agents

    def get(self, agent_id: str) -> Agent | None:
        return self.agents.get(agent_id)

    @staticmethod
    def _skill_matches(keyword: str, skill: str) -> bool:
        """Whether a task keyword matches an agent skill.

        Exact matches always count, at any length (a genuine "c" programming
        task must still find the C/C++ agent). Substring matches count only
        when BOTH sides are at least 3 characters: the registry derives some
        skills from name tokens, producing junk fragments ("c", "a", "b",
        "to", "up", "x") that otherwise substring-match almost any keyword
        and hijack routing — the audit of 2026-11-01 found the C/C++ agent
        absorbing 28 unrelated healed tasks (architecture, documentation,
        product requirements) through exactly this hole, in both primary
        assignment and the Level-1 self-healing reassignment path, which
        share this function.
        """
        if keyword == skill:
            return True
        if len(keyword) < 3 or len(skill) < 3:
            return False
        return keyword in skill or skill in keyword

    def find_by_skill(self, keywords: list[str], department_id: str | None = None,
                      exclude: set[str] | None = None) -> Agent | None:
        """Best available specialist whose skills match the most keywords."""
        best, best_score = None, 0
        for a in self.list_agents(department_id):
            if a.role != "SPECIALIST" or a.status in ("DISABLED", "QUARANTINED", "OFFLINE"):
                continue
            if exclude and a.agent_id in exclude:
                continue
            # Exact skill matches outweigh substring matches 3:1.
            score = sum((3 if k in a.skills else 1)
                        for k in keywords if any(self._skill_matches(k, s) for s in a.skills))
            if a.status == "IDLE":
                score += 0.1
            if score > best_score:
                best, best_score = a, score
        return best

    def set_status(self, agent_id: str, status: str) -> Agent | None:
        with self._lock:
            a = self.agents.get(agent_id)
            if a:
                a.status = status
            return a


REGISTRY = Registry()
