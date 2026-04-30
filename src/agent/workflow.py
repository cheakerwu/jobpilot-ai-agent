"""
轻量级 Agent 工作流状态机
"""
import json
import traceback
from datetime import datetime
from .state import JobAgentState


class Step:
    def __init__(self, name: str, fn):
        self.name = name
        self.fn = fn


class JobAnalysisWorkflow:
    """
    岗位分析 Agent 工作流。
    节点: parse_jd → load_evidence → score_match → llm_analyze → persist_result
    每一步的执行状态都被记录到 DB (AgentRun / AgentStep)。
    """

    def __init__(self, db, analyzer, profile: dict, user_id: int = 1):
        self.db = db
        self.analyzer = analyzer
        self.profile = profile
        self.user_id = user_id
        self._steps = [
            Step("parse_jd", self._step_parse_jd),
            Step("load_evidence", self._step_load_evidence),
            Step("score_match", self._step_score_match),
            Step("persist_result", self._step_persist_result),
        ]

    def run(self, job_id: int) -> dict:
        """执行完整工作流，返回最终状态字典"""
        job = self.db.get_job_by_id(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}

        state: JobAgentState = {
            "user_id": self.user_id,
            "job_id": job_id,
            "job": self._job_to_dict(job),
            "profile": self.profile,
            "evidence": [],
            "parsed_jd": {},
            "match_result": {},
            "analysis": {},
            "errors": [],
            "steps": [],
        }

        run = self.db.create_agent_run({
            "user_id": self.user_id,
            "job_id": job_id,
            "workflow_name": "job_analysis",
            "status": "running",
            "input_json": json.dumps({"job_id": job_id}, ensure_ascii=False),
        })
        if not run:
            return {"success": False, "error": "无法创建 AgentRun 记录"}

        for step in self._steps:
            db_step = self.db.add_agent_step({
                "run_id": run.id,
                "step_name": step.name,
                "status": "running",
                "started_at": datetime.now(),
            })
            step_record = {"name": step.name, "status": "running"}
            state["steps"].append(step_record)

            try:
                state = step.fn(state)
                step_record["status"] = "completed"
                if db_step:
                    self.db.update_agent_step(db_step.id, status="completed",
                                              finished_at=datetime.now())
            except Exception as e:
                err = {"step": step.name, "error": str(e), "trace": traceback.format_exc()}
                state["errors"].append(err)
                step_record["status"] = "failed"
                if db_step:
                    self.db.update_agent_step(db_step.id, status="failed",
                                              error_message=str(e), finished_at=datetime.now())
                self.db.update_agent_run(run.id, status="failed",
                                         error_message=str(e), finished_at=datetime.now())
                return {"success": False, "run_id": run.id, "error": str(e), "state": state}

        self.db.update_agent_run(run.id, status="completed",
                                  output_json=json.dumps(state.get("analysis", {}), ensure_ascii=False),
                                  finished_at=datetime.now())
        return {"success": True, "run_id": run.id, "analysis": state.get("analysis", {})}

    # ── Steps ──────────────────────────────────────────────────────────────

    def _step_parse_jd(self, state: JobAgentState) -> JobAgentState:
        """解析 JD 结构（规则解析，后续可升级为 LLM 解析）"""
        job = state["job"]
        text = f"{job.get('description','')} {job.get('requirements','')}".lower()
        state["parsed_jd"] = {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("city", ""),
            "salary_range": job.get("salary", ""),
            "raw_text": text[:500],
        }
        return state

    def _step_load_evidence(self, state: JobAgentState) -> JobAgentState:
        """从证据库加载当前用户的所有证据"""
        evidence_items = self.db.get_evidence_list(user_id=state.get("user_id", 1))
        state["evidence"] = [
            {
                "id": ev.id,
                "type": ev.type,
                "title": ev.title,
                "content": ev.content,
                "skill_tags": ev.get_skill_tags(),
                "confidence": ev.confidence,
            }
            for ev in evidence_items
        ]
        return state

    def _step_score_match(self, state: JobAgentState) -> JobAgentState:
        """调用分析器进行评分"""
        result = self.analyzer.analyze(
            job=state["job"],
            profile=state["profile"],
            evidence=state["evidence"],
        )
        state["match_result"] = {
            "match_score": result.match_score,
            "risk_score": result.risk_score,
            "recommendation_level": result.recommendation_level,
        }
        state["analysis"] = {
            "match_score": result.match_score,
            "risk_score": result.risk_score,
            "recommendation_level": result.recommendation_level,
            "summary": result.summary,
            "action_suggestion": result.action_suggestion,
            "matched_evidence": result.matched_evidence,
            "gaps": result.gaps,
            "risks": result.risks,
            "do_not_exaggerate": result.do_not_exaggerate,
            "parsed_jd": result.parsed_jd,
            "analyzer_type": result.analyzer_type,
        }
        return state

    def _step_persist_result(self, state: JobAgentState) -> JobAgentState:
        """将分析结果持久化到数据库"""
        analysis = state["analysis"]
        saved = self.db.save_analysis({
            "job_id": state["job_id"],
            "user_id": state.get("user_id", 1),
            "match_score": analysis.get("match_score"),
            "risk_score": analysis.get("risk_score"),
            "recommendation_level": analysis.get("recommendation_level"),
            "summary": analysis.get("summary"),
            "action_suggestion": analysis.get("action_suggestion"),
            "matched_evidence_json": analysis.get("matched_evidence", []),
            "gaps_json": analysis.get("gaps", []),
            "risks_json": analysis.get("risks", []),
            "do_not_exaggerate_json": analysis.get("do_not_exaggerate", []),
            "parsed_jd_json": analysis.get("parsed_jd", {}),
            "analyzer_type": analysis.get("analyzer_type", "hybrid"),
        })

        if saved:
            state["analysis"]["analysis_id"] = saved.id
            # 更新岗位状态
            level = analysis.get("recommendation_level", "C")
            new_status = "recommended" if level in ("A", "B") else "analyzed"
            self.db.update_job(state["job_id"], status=new_status,
                               match_score=analysis.get("match_score"))

        return state

    # ── Helpers ────────────────────────────────────────────────────────────

    def _job_to_dict(self, job) -> dict:
        return {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "salary": job.salary,
            "description": job.description or "",
            "requirements": job.requirements or "",
            "url": job.url or "",
            "source": job.source,
            "status": job.status,
        }
