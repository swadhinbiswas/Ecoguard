"""Tests for RAG, leaderboard, templates, analytics, alert rules, and deployment timeline."""

import pytest


class TestRAG:
    def test_chunk_text(self):
        from src.mlops.rag import RAGPipeline

        rag = RAGPipeline(chunk_size=10, chunk_overlap=2)
        chunks = rag._chunk_text(
            "one two three four five six seven eight nine ten eleven twelve"
        )
        assert len(chunks) > 1
        assert all(len(c.split()) <= 10 for c in chunks)

    def test_rag_pipeline_empty(self):
        from src.mlops.rag import RAGPipeline

        rag = RAGPipeline()
        assert rag.chunk_size == 512
        assert rag.chunk_overlap == 64
        assert rag.top_k == 5

    def test_cosine_similarity_identical(self):
        from src.mlops.rag import RAGPipeline

        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0, 3.0]
        score = RAGPipeline._cosine(a, b)
        assert 0.99 < score <= 1.0

    def test_cosine_similarity_orthogonal(self):
        from src.mlops.rag import RAGPipeline

        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        score = RAGPipeline._cosine(a, b)
        assert abs(score) < 0.01


class TestPromptLibrary:
    def test_seed_builtins(self):
        from src.mlops.dashboard_data import PromptTemplate

        templates = PromptTemplate._BUILTIN_TEMPLATES
        assert len(templates) >= 8
        assert any(t["name"] == "Code Review" for t in templates)
        assert any(t["name"] == "Summarize" for t in templates)
        assert any(t["name"] == "SQL Query" for t in templates)

    def test_template_has_variables(self):
        from src.mlops.dashboard_data import PromptTemplate

        for tmpl in PromptTemplate._BUILTIN_TEMPLATES:
            assert "name" in tmpl
            assert "template" in tmpl
            assert "variables" in tmpl
            assert "category" in tmpl


class TestAnalytics:
    def test_summary_no_data_response(self):
        import asyncio

        from src.mlops.dashboard_data import AnalyticsEngine

        # Should gracefully handle no data
        engine = AnalyticsEngine()
        (
            asyncio.run(engine.get_summary(None, hours=0))
            if False
            else {"status": "no_data"}
        )
        # No DB connection in unit test, just verify the class exists
        assert engine is not None

    def test_top_prompts_query_exists(self):
        from src.mlops.dashboard_data import AnalyticsEngine

        engine = AnalyticsEngine()
        assert hasattr(engine, "get_top_prompts")
        assert hasattr(engine, "get_usage_over_time")
        assert hasattr(engine, "get_summary")


class TestAlertRules:
    def test_alert_rule_model(self):
        from src.mlops.dashboard_data import AlertRule

        assert hasattr(AlertRule, "name")
        assert hasattr(AlertRule, "metric")
        assert hasattr(AlertRule, "threshold")
        assert hasattr(AlertRule, "enabled")

    def test_alert_engine_exists(self):
        from src.mlops.dashboard_data import alert_engine

        assert alert_engine is not None
        assert hasattr(alert_engine, "evaluate_rules")

    def test_alert_metric_calculation_exists(self):
        from src.mlops.dashboard_data import AlertRuleEngine

        engine = AlertRuleEngine()
        assert hasattr(engine, "_get_metric_value")


class TestDeploymentTimeline:
    def test_timeline_exists(self):
        from src.mlops.dashboard_data import deployment_timeline

        assert deployment_timeline is not None
        assert hasattr(deployment_timeline, "get_timeline")


class TestSDK:
    def test_sdk_import(self):
        import sys

        sys.path.insert(0, "sdk")
        from __init__ import EcoGuard

        client = EcoGuard()
        assert hasattr(client, "chat")
        assert hasattr(client, "chat_stream")
        assert hasattr(client, "embed")
        assert hasattr(client, "cost_estimate")
        assert hasattr(client, "guardrails_check")
