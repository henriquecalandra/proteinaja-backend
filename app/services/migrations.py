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
        _add_coluna(
            engine,
            "pedidos",
            "metodo_pagamento",
            {
                "postgresql": "VARCHAR(20)",
                "sqlite": "VARCHAR(20)",
            },
        )
        _add_coluna(
            engine,
            "pedidos",
            "pago",
            {
                "postgresql": "BOOLEAN NOT NULL DEFAULT FALSE",
                "sqlite": "BOOLEAN NOT NULL DEFAULT 0",
            },
        )
        _add_coluna(
            engine,
            "pedidos",
            "link_pagamento",
            {
                "postgresql": "TEXT",
                "sqlite": "TEXT",
            },
        )
        # Multi-tenant: colunas em 'usuarios'.
        _add_coluna(
            engine,
            "usuarios",
            "role",
            {
                "postgresql": "VARCHAR(20) NOT NULL DEFAULT 'empresa'",
                "sqlite": "VARCHAR(20) NOT NULL DEFAULT 'empresa'",
            },
        )
        _add_coluna(
            engine,
            "usuarios",
            "empresa_id",
            {
                "postgresql": "INTEGER",
                "sqlite": "INTEGER",
            },
        )
        # Multi-tenant REAL: coluna empresa_id (INTEGER nullable, SEM default,
        # SEM NOT NULL) nas tabelas de dados. Idempotente e defensivo.
        for tabela in ("clientes", "produtos", "conversas", "pedidos"):
            _add_coluna(
                engine,
                tabela,
                "empresa_id",
                {
                    "postgresql": "INTEGER",
                    "sqlite": "INTEGER",
                },
            )
        # Cadastro completo da empresa: 5 colunas de texto em 'empresas'.
        # VARCHAR/TEXT, nullable, sem default (NAO sao INTEGER).
        for coluna, tipo in (
            ("email_contato", "VARCHAR(200)"),
            ("telefone", "VARCHAR(40)"),
            ("endereco", "TEXT"),
            ("responsavel", "VARCHAR(200)"),
            ("segmento", "VARCHAR(40)"),
        ):
            _add_coluna(
                engine,
                "empresas",
                coluna,
                {"postgresql": tipo, "sqlite": tipo},
            )
        # Cadastro completo de produtos: 6 colunas novas em 'produtos'.
        # Idempotente e defensivo (reusa _add_coluna).
        _add_coluna(
            engine,
            "produtos",
            "sku",
            {"postgresql": "VARCHAR(60)", "sqlite": "VARCHAR(60)"},
        )
        _add_coluna(
            engine,
            "produtos",
            "unidade",
            {
                "postgresql": "VARCHAR(8) NOT NULL DEFAULT 'kg'",
                "sqlite": "VARCHAR(8) NOT NULL DEFAULT 'kg'",
            },
        )
        _add_coluna(
            engine,
            "produtos",
            "estoque",
            {
                "postgresql": "DOUBLE PRECISION NOT NULL DEFAULT 0",
                "sqlite": "FLOAT NOT NULL DEFAULT 0",
            },
        )
        _add_coluna(
            engine,
            "produtos",
            "estoque_minimo",
            {
                "postgresql": "DOUBLE PRECISION NOT NULL DEFAULT 0",
                "sqlite": "FLOAT NOT NULL DEFAULT 0",
            },
        )
        _add_coluna(
            engine,
            "produtos",
            "preco_custo",
            {"postgresql": "DOUBLE PRECISION", "sqlite": "FLOAT"},
        )
        _add_coluna(
            engine,
            "produtos",
            "descricao",
            {"postgresql": "TEXT", "sqlite": "TEXT"},
        )
        # Remove a UNIQUE legada de produtos.nome (criada no Postgres antes do
        # multi-tenant). Produtos agora sao por empresa -> o nome NAO e mais
        # unico global. create_all/_add_coluna nao removem constraints; fazemos
        # explicitamente. Defensivo e idempotente (IF EXISTS).
        _drop_unique_produtos_nome(engine)
    except Exception:
        logger.exception("migrations: ensure_schema falhou (ignorado)")


def _drop_unique_produtos_nome(engine: Engine) -> None:
    """Remove constraint/indice UNIQUE de produtos.nome (Postgres). Nunca levanta."""
    try:
        if engine.dialect.name != "postgresql":
            return  # SQLite local ja cria a tabela sem unique no model atual
        insp = inspect(engine)
        for uc in insp.get_unique_constraints("produtos"):
            if uc.get("column_names") == ["nome"] and uc.get("name"):
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE produtos DROP CONSTRAINT IF EXISTS "{uc["name"]}"'))
                logger.info("migrations: unique constraint %s removida de produtos.nome", uc["name"])
        for ix in insp.get_indexes("produtos"):
            if ix.get("unique") and ix.get("column_names") == ["nome"] and ix.get("name"):
                with engine.begin() as conn:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{ix["name"]}"'))
                logger.info("migrations: unique index %s removido de produtos.nome", ix["name"])
    except Exception:
        logger.exception("migrations: falha ao remover unique de produtos.nome (ignorado)")
