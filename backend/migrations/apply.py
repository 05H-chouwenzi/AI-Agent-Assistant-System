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


def run():
    sql_file = MIGRATIONS_DIR / "001_add_indexes.sql"
    print(f"正在执行迁移: {sql_file.name} ...")

    with engine.connect() as conn:
        sql = sql_file.read_text(encoding="utf-8")
        # 拆分为独立语句，忽略注释行和空行
        statements = [
            s.strip()
            for s in sql.split(";")
            if s.strip() and not s.strip().startswith("--")
        ]
        for stmt in statements:
            stmt_clean = stmt.strip()
            if stmt_clean:
                print(f"  执行: {stmt_clean[:80]}...")
                conn.execute(text(stmt_clean))
        conn.commit()

    print("迁移完成!")


if __name__ == "__main__":
    run()
