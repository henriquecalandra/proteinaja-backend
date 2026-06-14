"""
Migracao leve de schema para o ProteinaJa.

Base.metadata.create_all NAO adiciona colunas novas a tabelas que ja existem
(ex.: Postgres do Render). Este modulo garante, de forma idempotente e
DEFENSIVA, que colunas adicionadas depois da criacao inicial do banco existam.

Uso: chamar ensure_schema(engine) no startup, LOGO APOS create_all e ANTES do
seed.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migrations")


def _coluna_existe(engine: Engine, tabela: str, coluna: str) -> bool:
    """Retorna True se a coluna existir na tabela. Defensivo: erro -> assume que existe."""
    try:
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns(tabela)}
        return coluna in cols
    except Exception:
        logger.exception(
            "migrations: falha ao inspecionar %s.%s (assumindo que existe)",
            tabela,
            coluna,
        )
        return True


def _add_coluna(engine: Engine, tabela: str, coluna: str, ddl_tipo: dict[str, str]) -> None:
    """Executa ALTER TABLE ... ADD COLUMN se a coluna faltar. Nunca levanta."""
    try:
        if _coluna_existe(engine, tabela, coluna):
            return
        dialect = engine.dialect.name
        tipo = ddl_tipo.get(dialect)
        if tipo is None:
            # Dialect nao mapeado: usa o do Postgres como padrao razoavel.
            tipo = ddl_tipo.get("postgresql") or next(iter(ddl_tipo.values()))
        sql = f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"
        with engine.begin() as conn:
            conn.execute(text(sql))
        logger.info("migrations: coluna %s.%s adicionada (%s)", tabela, coluna, dialect)
    except Exception:
        logger.exception(
            "migrations: falha ao adicionar coluna %s.%s (ignorado)", tabela, coluna
        )


def ensure_schema(engine: Engine) -> None:
    """Garante colunas adicionadas apos a criacao inicial do banco.

    Idempotente (so adiciona se faltar) e defensivo (nunca levanta excecao).
    """
    try:
        _add_coluna(
            engine,
            "clientes",
            "atendido_por_ia",
            {
                "postgresql": "BOOLEAN NOT NULL DEFAULT TRUE",
                "sqlite": "BOOLEAN NOT NULL DEFAULT 1",
            },
        )
    except Exception:
        logger.exception("migrations: ensure_schema falhou (ignorado)")
