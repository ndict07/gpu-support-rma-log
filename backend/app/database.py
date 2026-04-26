from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'support_logs.sqlite3'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_sqlite()


def migrate_sqlite() -> None:
    expected_message_columns = {
        "attachment_url": "TEXT",
        "attachment_filename": "VARCHAR(255)",
        "attachment_mime_type": "VARCHAR(255)",
        "attachment_size": "INTEGER",
    }
    expected_thread_columns = {
        "title": "VARCHAR(255)",
        "customer_name": "VARCHAR(255)",
    }

    with engine.begin() as connection:
        existing_messages = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(messages)")).all()
        }
        for column_name, column_type in expected_message_columns.items():
            if column_name not in existing_messages:
                connection.execute(
                    text(f"ALTER TABLE messages ADD COLUMN {column_name} {column_type}")
                )

        existing_threads = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(rma_threads)")).all()
        }
        for column_name, column_type in expected_thread_columns.items():
            if column_name not in existing_threads:
                connection.execute(
                    text(f"ALTER TABLE rma_threads ADD COLUMN {column_name} {column_type}")
                )
