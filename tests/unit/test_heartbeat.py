"""
tests/unit/test_heartbeat.py

Tests for heartbeat scheduler.
"""

import pytest
from src.core.heartbeat import _default_heartbeat_task, get_scheduler, list_jobs


class TestHeartbeat:
    def test_default_task_ceo(self):
        assert _default_heartbeat_task("ceo") == "weekly_synthesis"

    def test_default_task_finance(self):
        assert _default_heartbeat_task("finance") == "budget_status"

    def test_default_task_scout(self):
        assert _default_heartbeat_task("scout") == "competitor_scan"

    def test_default_task_performance(self):
        assert _default_heartbeat_task("performance") == "daily_performance_check"

    def test_default_task_ops(self):
        assert _default_heartbeat_task("ops") == "compliance_check"

    def test_default_task_unknown(self):
        assert _default_heartbeat_task("unknown_agent") == "heartbeat_check"

    def test_scheduler_instance(self):
        scheduler = get_scheduler()
        assert scheduler is not None

    def test_list_jobs_empty(self):
        jobs = list_jobs()
        assert isinstance(jobs, list)
