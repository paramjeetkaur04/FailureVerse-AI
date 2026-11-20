"""Reviewed additive migration: no ALTER, DROP, or rewriting existing records."""
from sqlalchemy import inspect, text

from app.models.workflow import WorkflowRecord


def migrate_workflows(engine):
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)'))
        if connection.execute(text('SELECT version FROM schema_versions WHERE version=1')).first() is None:
            WorkflowRecord.__table__.create(connection, checkfirst=True)
            actual = {column['name'] for column in inspect(connection).get_columns('agent_workflows')}
            if actual != set(WorkflowRecord.__table__.columns.keys()):
                raise RuntimeError('Workflow schema does not match migration version 1; storage requires review.')
            connection.execute(text("INSERT INTO schema_versions(version, applied_at) VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ','now'))"))
