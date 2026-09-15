import os
import aiosqlite
from backend.config import settings


async def ensure_db_dir():
    db_path = settings.get_database_path
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


async def get_db():
    await ensure_db_dir()
    db = await aiosqlite.connect(settings.get_database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await db.execute("PRAGMA journal_mode = WAL;")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    await ensure_db_dir()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    async with aiosqlite.connect(settings.get_database_path) as db:
        await db.executescript(schema_sql)
        await db.commit()
