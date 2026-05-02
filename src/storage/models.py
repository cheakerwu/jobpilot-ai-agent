"""
数据模型定义
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    ai_usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Job(Base):
    """岗位表"""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=False)
    city = Column(String(50), index=True)
    salary = Column(String(100))
    description = Column(Text)
    requirements = Column(Text)
    platform = Column(String(20), default='manual', index=True)
    source = Column(String(50), default='manual', index=True)  # manual/csv/remoteok/ats/etc.
    url = Column(String(500))
    status = Column(String(30), default='new', index=True)
    # 状态: new/analyzed/recommended/resume_generated/to_apply/applied/screening/interviewing/offer/rejected/archived
    match_score = Column(Integer)
    user_id = Column(Integer, index=True, default=1)  # 预留多用户
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    applications = relationship("Application", back_populates="job")
    analyses = relationship("JobAnalysis", back_populates="job")
    resume_versions = relationship("ResumeVersion", back_populates="job")

    __table_args__ = (
        Index('idx_status_city', 'status', 'city'),
        Index('idx_platform_status', 'platform', 'status'),
        Index('idx_job_user_status', 'user_id', 'status'),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}')>"


class Application(Base):
    """投递记录表"""
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    user_id = Column(Integer, index=True, default=1)
    resume_path = Column(String(500))
    resume_version_id = Column(Integer, ForeignKey('resume_versions.id'), nullable=True)
    applied_at = Column(DateTime, default=datetime.now)
    status = Column(String(30), default='to_apply', index=True)
    # 状态: to_apply/applied/screening/interviewing/offer/rejected/archived
    feedback = Column(Text)
    notes = Column(Text)

    job = relationship("Job", back_populates="applications")
    resume_version = relationship("ResumeVersion")

    def __repr__(self):
        return f"<Application(id={self.id}, job_id={self.job_id}, status='{self.status}')>"


class EvidenceItem(Base):
    """个人经历证据库"""
    __tablename__ = 'evidence_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    type = Column(String(50), nullable=False, index=True)
    # 类型: skill/project/work_experience/education/achievement/certificate/portfolio
    title = Column(String(200), nullable=False)
    content = Column(Text)
    skill_tags = Column(Text)  # JSON array string: ["Python", "FastAPI"]
    source = Column(String(100), default='user_profile')
    confidence = Column(Float, default=0.9)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def get_skill_tags(self) -> list:
        import json
        if self.skill_tags:
            try:
                return json.loads(self.skill_tags)
            except Exception:
                return []
        return []

    __table_args__ = (
        Index('idx_evidence_user_type', 'user_id', 'type'),
    )

    def __repr__(self):
        return f"<EvidenceItem(id={self.id}, type='{self.type}', title='{self.title}')>"


class JobImportBatch(Base):
    """岗位导入批次记录"""
    __tablename__ = 'job_import_batches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    source = Column(String(50), nullable=False)  # manual/csv/remoteok/etc.
    filename = Column(String(500))
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<JobImportBatch(id={self.id}, source='{self.source}', success={self.success_count})>"


class JobAnalysis(Base):
    """岗位分析结果"""
    __tablename__ = 'job_analyses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    user_id = Column(Integer, index=True, default=1)
    match_score = Column(Integer)           # 0-100
    risk_score = Column(Integer)            # 0-100
    recommendation_level = Column(String(5))  # A/B/C/D
    summary = Column(Text)
    action_suggestion = Column(Text)
    matched_evidence_json = Column(Text)    # JSON
    gaps_json = Column(Text)               # JSON
    risks_json = Column(Text)              # JSON
    do_not_exaggerate_json = Column(Text)  # JSON
    parsed_jd_json = Column(Text)          # JSON: structured JD fields
    analyzer_type = Column(String(50), default='hybrid')  # rule/llm/hybrid
    created_at = Column(DateTime, default=datetime.now, index=True)

    job = relationship("Job", back_populates="analyses")

    def __repr__(self):
        return f"<JobAnalysis(id={self.id}, job_id={self.job_id}, level='{self.recommendation_level}')>"


class ResumeVersion(Base):
    """定制简历版本"""
    __tablename__ = 'resume_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey('job_analyses.id'), nullable=True)
    title = Column(String(200))
    content = Column(Text, nullable=False)
    format = Column(String(20), default='markdown')
    file_path = Column(String(500))
    evidence_links_json = Column(Text)    # JSON: [{evidence_id, bullet_text}]
    changed_sections_json = Column(Text)  # JSON: [section_name]
    risk_warnings_json = Column(Text)     # JSON: [warning_text]
    keyword_coverage_json = Column(Text)  # JSON: {keyword: bool}
    created_at = Column(DateTime, default=datetime.now, index=True)

    job = relationship("Job", back_populates="resume_versions")
    analysis = relationship("JobAnalysis")

    def __repr__(self):
        return f"<ResumeVersion(id={self.id}, job_id={self.job_id})>"


class CoverLetter(Base):
    """求职信"""
    __tablename__ = 'cover_letters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey('job_analyses.id'), nullable=True)
    title = Column(String(200))
    content = Column(Text, nullable=False)
    format = Column(String(20), default='markdown')
    evidence_links_json = Column(Text)    # JSON: [{evidence_id, bullet_text}]
    highlights_json = Column(Text)        # JSON: [str]
    tone = Column(String(50), default='professional')
    created_at = Column(DateTime, default=datetime.now, index=True)

    job = relationship("Job")
    analysis = relationship("JobAnalysis")

    def __repr__(self):
        return f"<CoverLetter(id={self.id}, job_id={self.job_id})>"


class InterviewPrep(Base):
    """面试准备材料"""
    __tablename__ = 'interview_preps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey('job_analyses.id'), nullable=True)
    title = Column(String(200))
    questions_json = Column(Text)            # JSON: [{category, question, answer, evidence_refs}]
    company_insights_json = Column(Text)     # JSON: {culture, tech_stack, interview_process}
    preparation_tips_json = Column(Text)     # JSON: [str]
    risk_areas_json = Column(Text)           # JSON: [{area, suggestion}]
    format = Column(String(20), default='markdown')
    created_at = Column(DateTime, default=datetime.now, index=True)

    job = relationship("Job")
    analysis = relationship("JobAnalysis")

    def __repr__(self):
        return f"<InterviewPrep(id={self.id}, job_id={self.job_id})>"


class AgentRun(Base):
    """Agent 执行记录"""
    __tablename__ = 'agent_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, default=1)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True, index=True)
    workflow_name = Column(String(100), nullable=False)
    status = Column(String(30), default='pending', index=True)
    # 状态: pending/running/completed/failed
    input_json = Column(Text)
    output_json = Column(Text)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)

    steps = relationship("AgentStep", back_populates="run", order_by="AgentStep.id")

    def __repr__(self):
        return f"<AgentRun(id={self.id}, workflow='{self.workflow_name}', status='{self.status}')>"


class AgentStep(Base):
    """Agent 步骤记录"""
    __tablename__ = 'agent_steps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('agent_runs.id'), nullable=False, index=True)
    step_name = Column(String(100), nullable=False)
    status = Column(String(30), default='pending')
    input_json = Column(Text)
    output_json = Column(Text)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)

    run = relationship("AgentRun", back_populates="steps")

    def __repr__(self):
        return f"<AgentStep(id={self.id}, run_id={self.run_id}, step='{self.step_name}')>"
