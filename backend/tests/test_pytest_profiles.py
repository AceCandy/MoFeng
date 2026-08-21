# AIMETA P=pytest测试分层契约|R=PostgreSQL_fixture_marker分类|NR=不启动数据库或Docker|E=test_postgres_marker_is_applied_only_to_database_fixtures|X=internal|A=单元测试|D=pytest,stdlib|S=none|RD=./conftest.py
from types import SimpleNamespace
from unittest.mock import Mock

import conftest as test_fixtures


def test_postgres_marker_is_applied_only_to_database_fixtures() -> None:
    fixture_names = ("_pg_engine", "db_session_factory", "isolated_pg", "tmp_path")
    items = [
        SimpleNamespace(fixturenames=[fixture_name], add_marker=Mock())
        for fixture_name in fixture_names
    ]

    test_fixtures.pytest_collection_modifyitems(items)

    assert [item.add_marker.call_count for item in items] == [1, 1, 1, 0]
    assert all(item.add_marker.call_args.args[0].name == "postgres" for item in items[:3])
