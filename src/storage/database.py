"""
数据库管理器
"""
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, desc, text
from sqlalchemy.orm import sessionmaker
from .models import (
    Base, Job, Application, EvidenceItem, JobImportBatch,
    JobAnalysis, ResumeVersion, AgentRun, AgentStep,
)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str = 'data/jobs.db'):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        self._migrate_sqlite_schema()
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def _migrate_sqlite_schema(self):
        """补齐旧版 SQLite 数据库缺失的列，保留已有岗位数据。"""
        if self.engine.dialect.name != "sqlite":
            return

        migrations = {
            "jobs": {
                "source": "ALTER TABLE jobs ADD COLUMN source VARCHAR(50) DEFAULT 'manual'",
                "user_id": "ALTER TABLE jobs ADD COLUMN user_id INTEGER DEFAULT 1",
            },
            "applications": {
                "user_id": "ALTER TABLE applications ADD COLUMN user_id INTEGER DEFAULT 1",
                "resume_version_id": "ALTER TABLE applications ADD COLUMN resume_version_id INTEGER",
                "feedback": "ALTER TABLE applications ADD COLUMN feedback TEXT",
            },
        }

        with self.engine.begin() as conn:
            existing_tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            }
            for table, columns in migrations.items():
                if table not in existing_tables:
                    continue
                existing_columns = {
                    row[1]
                    for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                }
                for column, ddl in columns.items():
                    if column not in existing_columns:
                        conn.execute(text(ddl))

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def add_job(self, job_data: dict) -> Job | None:
        try:
            job = Job(**job_data)
            self.session.add(job)
            self.session.commit()
            return job
        except Exception as e:
            self.session.rollback()
            print(f"添加岗位失败: {e}")
            return None

    def get_job_by_id(self, job_id: int) -> Job | None:
        return self.session.query(Job).filter(Job.id == job_id).first()

    def get_job_by_platform_id(self, platform_id: str) -> Job | None:
        return self.session.query(Job).filter(Job.job_id == platform_id).first()

    def get_all_jobs(self, status: str | None = None, limit: int | None = None) -> list[Job]:
        query = self.session.query(Job)
        if status:
            query = query.filter(Job.status == status)
        query = query.order_by(desc(Job.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_job(self, job_id: int, **kwargs) -> Job | None:
        try:
            job = self.get_job_by_id(job_id)
            if job:
                for key, value in kwargs.items():
                    setattr(job, key, value)
                self.session.commit()
                return job
            return None
        except Exception as e:
            self.session.rollback()
            print(f"更新岗位失败: {e}")
            return None

    def get_jobs_paginated(
        self, page: int = 1, per_page: int = 20,
        status: str | None = None, city: str | None = None,
    ) -> list[Job]:
        query = self.session.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if city:
            query = query.filter(Job.city == city)
        query = query.order_by(desc(Job.created_at))
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page).all()

    def get_jobs_count(self, status: str | None = None, city: str | None = None) -> int:
        query = self.session.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if city:
            query = query.filter(Job.city == city)
        return query.count()

    def get_statistics(self) -> dict:
        return {
            'total': self.session.query(Job).count(),
            'new': self.session.query(Job).filter(Job.status == 'new').count(),
            'analyzed': self.session.query(Job).filter(Job.status == 'analyzed').count(),
            'recommended': self.session.query(Job).filter(Job.status == 'recommended').count(),
            'applied': self.session.query(Job).filter(Job.status == 'applied').count(),
            'interviewing': self.session.query(Job).filter(Job.status == 'interviewing').count(),
            'offer': self.session.query(Job).filter(Job.status == 'offer').count(),
        }

    # ── Applications ─────────────────────────────────────────────────────────

    def add_application(self, job_id: int, resume_path: str = None, notes: str = None) -> Application | None:
        try:
            application = Application(job_id=job_id, resume_path=resume_path, notes=notes)
            self.session.add(application)
            job = self.get_job_by_id(job_id)
            if job:
                job.status = 'applied'
            self.session.commit()
            return application
        except Exception as e:
            self.session.rollback()
            print(f"添加投递记录失败: {e}")
            return None

    def get_applications(self, limit: int | None = None) -> list[Application]:
        query = self.session.query(Application).order_by(desc(Application.applied_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_application(self, app_id: int, **kwargs) -> Application | None:
        try:
            app = self.session.query(Application).filter(Application.id == app_id).first()
            if app:
                for key, value in kwargs.items():
                    setattr(app, key, value)
                self.session.commit()
                return app
            return None
        except Exception as e:
            self.session.rollback()
            print(f"更新投递记录失败: {e}")
            return None

    # ── Evidence ─────────────────────────────────────────────────────────────

    def add_evidence(self, data: dict) -> EvidenceItem | None:
        try:
            if 'skill_tags' in data and isinstance(data['skill_tags'], list):
                data = {**data, 'skill_tags': json.dumps(data['skill_tags'], ensure_ascii=False)}
            item = EvidenceItem(**data)
            self.session.add(item)
            self.session.commit()
            return item
        except Exception as e:
            self.session.rollback()
            print(f"添加证据失败: {e}")
            return None

    def get_evidence_list(self, user_id: int = 1, type_filter: str | None = None) -> list[EvidenceItem]:
        query = self.session.query(EvidenceItem).filter(EvidenceItem.user_id == user_id)
        if type_filter:
            query = query.filter(EvidenceItem.type == type_filter)
        return query.order_by(EvidenceItem.type, EvidenceItem.id).all()

    def get_evidence_by_id(self, evidence_id: int) -> EvidenceItem | None:
        return self.session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()

    def update_evidence(self, evidence_id: int, **kwargs) -> EvidenceItem | None:
        try:
            item = self.get_evidence_by_id(evidence_id)
            if item:
                if 'skill_tags' in kwargs and isinstance(kwargs['skill_tags'], list):
                    kwargs['skill_tags'] = json.dumps(kwargs['skill_tags'], ensure_ascii=False)
                for key, value in kwargs.items():
                    setattr(item, key, value)
                item.updated_at = datetime.now()
                self.session.commit()
                return item
            return None
        except Exception as e:
            self.session.rollback()
            print(f"更新证据失败: {e}")
            return None

    def delete_evidence(self, evidence_id: int) -> bool:
        try:
            item = self.get_evidence_by_id(evidence_id)
            if item:
                self.session.delete(item)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"删除证据失败: {e}")
            return False

    # ── Import Batches ────────────────────────────────────────────────────────

    def create_import_batch(self, data: dict) -> JobImportBatch | None:
        try:
            batch = JobImportBatch(**data)
            self.session.add(batch)
            self.session.commit()
            return batch
        except Exception as e:
            self.session.rollback()
            print(f"创建导入批次失败: {e}")
            return None

    def update_import_batch(self, batch_id: int, **kwargs) -> JobImportBatch | None:
        try:
            batch = self.session.query(JobImportBatch).filter(JobImportBatch.id == batch_id).first()
            if batch:
                for key, value in kwargs.items():
                    setattr(batch, key, value)
                self.session.commit()
                return batch
            return None
        except Exception as e:
            self.session.rollback()
            return None

    def get_import_batch(self, batch_id: int) -> JobImportBatch | None:
        return self.session.query(JobImportBatch).filter(JobImportBatch.id == batch_id).first()

    # ── Job Analysis ──────────────────────────────────────────────────────────

    def save_analysis(self, data: dict) -> JobAnalysis | None:
        try:
            for field in ('matched_evidence_json', 'gaps_json', 'risks_json',
                          'do_not_exaggerate_json', 'parsed_jd_json'):
                if field in data and not isinstance(data[field], str):
                    data[field] = json.dumps(data[field], ensure_ascii=False)
            analysis = JobAnalysis(**data)
            self.session.add(analysis)
            self.session.commit()
            return analysis
        except Exception as e:
            self.session.rollback()
            print(f"保存分析结果失败: {e}")
            return None

    def get_analysis_by_job(self, job_id: int) -> JobAnalysis | None:
        return (
            self.session.query(JobAnalysis)
            .filter(JobAnalysis.job_id == job_id)
            .order_by(desc(JobAnalysis.created_at))
            .first()
        )

    def get_analysis_by_id(self, analysis_id: int) -> JobAnalysis | None:
        return self.session.query(JobAnalysis).filter(JobAnalysis.id == analysis_id).first()

    # ── Resume Versions ───────────────────────────────────────────────────────

    def save_resume_version(self, data: dict) -> ResumeVersion | None:
        try:
            for field in ('evidence_links_json', 'changed_sections_json',
                          'risk_warnings_json', 'keyword_coverage_json'):
                if field in data and not isinstance(data[field], str):
                    data[field] = json.dumps(data[field], ensure_ascii=False)
            rv = ResumeVersion(**data)
            self.session.add(rv)
            self.session.commit()
            return rv
        except Exception as e:
            self.session.rollback()
            print(f"保存简历版本失败: {e}")
            return None

    def get_resume_versions_by_job(self, job_id: int) -> list[ResumeVersion]:
        return (
            self.session.query(ResumeVersion)
            .filter(ResumeVersion.job_id == job_id)
            .order_by(desc(ResumeVersion.created_at))
            .all()
        )

    def get_resume_version_by_id(self, version_id: int) -> ResumeVersion | None:
        return self.session.query(ResumeVersion).filter(ResumeVersion.id == version_id).first()

    # ── Agent Runs ────────────────────────────────────────────────────────────

    def create_agent_run(self, data: dict) -> AgentRun | None:
        try:
            if 'input_json' in data and not isinstance(data['input_json'], str):
                data['input_json'] = json.dumps(data['input_json'], ensure_ascii=False)
            run = AgentRun(**data)
            self.session.add(run)
            self.session.commit()
            return run
        except Exception as e:
            self.session.rollback()
            print(f"创建 AgentRun 失败: {e}")
            return None

    def update_agent_run(self, run_id: int, **kwargs) -> AgentRun | None:
        try:
            run = self.session.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run:
                for key, value in kwargs.items():
                    if key in ('input_json', 'output_json') and not isinstance(value, str):
                        value = json.dumps(value, ensure_ascii=False)
                    setattr(run, key, value)
                self.session.commit()
                return run
            return None
        except Exception as e:
            self.session.rollback()
            return None

    def get_agent_run(self, run_id: int) -> AgentRun | None:
        return self.session.query(AgentRun).filter(AgentRun.id == run_id).first()

    def get_agent_runs(self, job_id: int | None = None, limit: int = 20) -> list[AgentRun]:
        query = self.session.query(AgentRun)
        if job_id:
            query = query.filter(AgentRun.job_id == job_id)
        return query.order_by(desc(AgentRun.started_at)).limit(limit).all()

    def add_agent_step(self, data: dict) -> AgentStep | None:
        try:
            for field in ('input_json', 'output_json'):
                if field in data and not isinstance(data[field], str):
                    data[field] = json.dumps(data[field], ensure_ascii=False)
            step = AgentStep(**data)
            self.session.add(step)
            self.session.commit()
            return step
        except Exception as e:
            self.session.rollback()
            print(f"添加 AgentStep 失败: {e}")
            return None

    def update_agent_step(self, step_id: int, **kwargs) -> AgentStep | None:
        try:
            step = self.session.query(AgentStep).filter(AgentStep.id == step_id).first()
            if step:
                for key, value in kwargs.items():
                    if key in ('input_json', 'output_json') and not isinstance(value, str):
                        value = json.dumps(value, ensure_ascii=False)
                    setattr(step, key, value)
                self.session.commit()
                return step
            return None
        except Exception as e:
            self.session.rollback()
            return None

    def close(self):
        if hasattr(self, 'session'):
            self.session.close()
        if hasattr(self, 'engine'):
            self.engine.dispose()
