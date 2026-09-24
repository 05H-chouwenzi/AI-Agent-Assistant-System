"""
应用数据库迁移 —— 逐个执行 SQL 文件中的语句
用法: python -m backend.migrations.apply
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.session import engine
from sqlalchemy import text


MIGRATIONS_DIR = Path(__file__).parent
MIGRATIONS = ["002_fix_system_logs_columns.sql", "003_knowledge_multimodal.sql"]


def run():
    for migration_name in MIGRATIONS:
        sql_file = MIGRATIONS_DIR / migration_name
        if not sql_file.exists():
            continue
        print(f"正在执行迁移: {sql_file.name} ...")

        with engine.connect() as conn:
            statements = [
                line.strip().rstrip(";")
                for line in sql_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            for statement in statements:
                if statement:
                    print(f"  执行: {statement[:80]}...")
                    conn.execute(text(statement))
            conn.commit()

    print("迁移完成!")


if __name__ == "__main__":
    run()
