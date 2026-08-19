import sqlite3
conn = sqlite3.connect('feynman.db')
c = conn.cursor()

cols = {'refresh_token_hash': 'TEXT', 'refresh_token_expires_at': 'DATETIME'}
for col, typ in cols.items():
    try:
        c.execute(f'ALTER TABLE users ADD COLUMN {col} {typ}')
        print(f'Added {col}')
    except Exception as e:
        print(f'Skip {col}: {e}')

c.execute("""CREATE TABLE IF NOT EXISTS quiz_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    document_session_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    total_questions INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    score_percent REAL NOT NULL DEFAULT 0.0,
    weak_topics TEXT NOT NULL DEFAULT '[]',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
)""")
print('quiz_sessions OK')

c.execute("""CREATE TABLE IF NOT EXISTS quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL DEFAULT 'MCQ',
    options_json TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    canonical_topic TEXT,
    source_page INTEGER,
    difficulty TEXT NOT NULL DEFAULT 'medium',
    order_index INTEGER NOT NULL DEFAULT 0
)""")
print('quiz_questions OK')

c.execute("""CREATE TABLE IF NOT EXISTS quiz_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    hints_used INTEGER NOT NULL DEFAULT 0,
    answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, question_id)
)""")
print('quiz_answers OK')

conn.commit()
conn.close()
print('Migration complete')
