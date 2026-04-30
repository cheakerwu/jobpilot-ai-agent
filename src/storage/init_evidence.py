"""
从 user_profile.json 初始化个人经历证据库
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.storage.database import DatabaseManager
from src.helpers import load_config


def init_evidence_from_profile(profile_path: str = 'config/user_profile.json',
                                db_path: str = None,
                                user_id: int = 1) -> int:
    """从 user_profile.json 初始化证据库，返回新增条目数"""
    config = load_config()
    db_path = db_path or config['storage']['db_path']
    db = DatabaseManager(db_path)

    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
    except FileNotFoundError:
        print(f"配置文件不存在: {profile_path}")
        return 0

    # 检查是否已初始化（避免重复）
    existing = db.get_evidence_list(user_id=user_id)
    if existing:
        print(f"证据库已有 {len(existing)} 条记录，跳过初始化")
        return 0

    count = 0
    basic = profile.get("basic_info", {})

    # 1. 技能列表
    skills = profile.get("skills", [])
    for skill in skills:
        db.add_evidence({
            "user_id": user_id,
            "type": "skill",
            "title": skill,
            "content": f"具备 {skill} 技能",
            "skill_tags": json.dumps([skill], ensure_ascii=False),
            "source": "user_profile",
            "confidence": 0.9,
        })
        count += 1

    # 2. 项目经历
    for exp in profile.get("experiences", []):
        tech_stack = exp.get("tech_stack", [])
        achievements = exp.get("achievements", [])
        content = exp.get("description", "")
        if achievements:
            content += "\n成果:\n" + "\n".join(f"- {a}" for a in achievements)
        db.add_evidence({
            "user_id": user_id,
            "type": "project",
            "title": exp.get("title", ""),
            "content": content,
            "skill_tags": json.dumps(tech_stack, ensure_ascii=False),
            "source": "user_profile",
            "confidence": 0.95,
        })
        count += 1

    # 3. 教育经历
    db.add_evidence({
        "user_id": user_id,
        "type": "education",
        "title": f"{basic.get('school', '')} {basic.get('education', '')}",
        "content": (
            f"学校: {basic.get('school', '')}\n"
            f"专业: {basic.get('education', '')}\n"
            f"毕业年份: {basic.get('graduation_year', '')}"
        ),
        "skill_tags": json.dumps([], ensure_ascii=False),
        "source": "user_profile",
        "confidence": 1.0,
    })
    count += 1

    print(f"证据库初始化完成，共导入 {count} 条证据")
    db.close()
    return count


if __name__ == "__main__":
    init_evidence_from_profile()
