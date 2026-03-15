"""
tests/unit/test_model_router.py  (AM-25)

Unit tests for src/core/model_router.py
"""

from __future__ import annotations

import pytest

from src.core.model_router import ModelRoute, route, supported_task_types
from src.shared.exceptions import ModelRouterError


class TestRoute:
    def test_strategy_routes_to_claude_opus(self) -> None:
        result = route("strategy")
        assert result == ModelRoute(model="claude-opus-4-6", provider="anthropic")

    def test_creative_routes_to_claude_sonnet(self) -> None:
        result = route("creative")
        assert result == ModelRoute(model="claude-sonnet-4-6", provider="anthropic")

    def test_batch_routes_to_llama_70b(self) -> None:
        result = route("batch")
        assert result == ModelRoute(model="llama3.3-70b", provider="cerebras")

    def test_monitoring_routes_to_llama_8b(self) -> None:
        result = route("monitoring")
        assert result == ModelRoute(model="llama3.1-8b", provider="cerebras")

    def test_unknown_task_type_raises_model_router_error(self) -> None:
        with pytest.raises(ModelRouterError) as exc_info:
            route("nonexistent_task")
        assert "nonexistent_task" in str(exc_info.value)

    def test_model_router_error_stores_task_type(self) -> None:
        try:
            route("bad_type")
        except ModelRouterError as e:
            assert e.task_type == "bad_type"

    def test_case_sensitive_task_type(self) -> None:
        """Task types are case-sensitive — 'Strategy' is not 'strategy'."""
        with pytest.raises(ModelRouterError):
            route("Strategy")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ModelRouterError):
            route("")


class TestSupportedTaskTypes:
    def test_returns_all_four_task_types(self) -> None:
        types = supported_task_types()
        assert set(types) == {"strategy", "creative", "batch", "monitoring"}

    def test_returns_list(self) -> None:
        assert isinstance(supported_task_types(), list)


class TestModelRoute:
    def test_model_route_is_frozen(self) -> None:
        mr = ModelRoute(model="test-model", provider="test-provider")
        with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
            mr.model = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ModelRoute(model="claude-opus-4-6", provider="anthropic")
        b = ModelRoute(model="claude-opus-4-6", provider="anthropic")
        assert a == b

    def test_inequality(self) -> None:
        a = ModelRoute(model="claude-opus-4-6", provider="anthropic")
        b = ModelRoute(model="claude-sonnet-4-6", provider="anthropic")
        assert a != b
