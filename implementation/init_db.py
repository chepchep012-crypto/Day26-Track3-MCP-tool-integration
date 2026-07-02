"""Creates and seeds the SQLite database used by the lab."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "lab.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    score REAL
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, email) VALUES
    ('Alice Nguyen', 'A1', 'alice@example.com'),
    ('Bao Tran', 'A1', 'bao@example.com'),
    ('Chi Le', 'A2', 'chi@example.com'),
    ('Duc Pham', 'A2', 'duc@example.com'),
    ('Emi Vo', 'A1', 'emi@example.com');

INSERT INTO courses (title, credits) VALUES
    ('Intro to Databases', 3),
    ('Python Programming', 4),
    ('Model Context Protocol', 3);

INSERT INTO enrollments (student_id, course_id, score) VALUES
    (1, 1, 92.5),
    (1, 2, 88.0),
    (2, 1, 75.0),
    (2, 3, 81.5),
    (3, 2, 90.0),
    (4, 3, 67.0),
    (5, 1, 95.0),
    (5, 3, 89.5);
"""


def create_database(db_path=None, reset=False):
    """
    1. Open SQLite database file.
    2. Execute schema SQL.
    3. Execute seed SQL if the database is empty (or reset is requested).
    4. Commit.
    5. Return database path.
    """
    path = Path(db_path or DB_PATH)

    if reset and path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute("SELECT COUNT(*) FROM students").fetchone()
        if row[0] == 0:
            conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    return str(path)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    path = create_database(reset=reset)
    print(f"Database ready at {path}")
