"""Tests for Durable Value Score module."""

import pytest

from instrument.value_score import (
    DurableValueScore,
    compute_dvs,
    compute_story_dvs,
    dvs_verdict_to_emoji,
)


class TestDurableValueScore:
    def test_serialization(self):
        dvs = DurableValueScore(
            correctness=0.9,
            architectural_fit=0.8,
            convention_adherence=0.85,
            session_cost=0.05,
            score=12.24,
            verdict="net_positive",
            has_review=True,
        )
        d = dvs.to_dict()
        assert d["correctness"] == 0.9
        assert d["verdict"] == "net_positive"
        assert d["provenance"]["has_review"] is True


class TestComputeDVS:
    def test_high_quality_low_cost_is_positive(self):
        dvs = compute_dvs(
            correctness=1.0,
            architectural_fit=0.9,
            convention_adherence=0.9,
            session_cost=0.01,
        )
        assert dvs.score > 1.0
        assert dvs.verdict == "net_positive"

    def test_low_quality_high_cost_is_negative(self):
        dvs = compute_dvs(
            correctness=0.3,
            architectural_fit=0.2,
            convention_adherence=0.2,
            session_cost=5.0,
        )
        assert dvs.score < 1.0
        assert dvs.verdict == "net_negative"

    def test_zero_cost_handled(self):
        dvs = compute_dvs(
            correctness=1.0,
            architectural_fit=1.0,
            convention_adherence=1.0,
            session_cost=0.0,
        )
        assert dvs.score > 0

    def test_with_sonar_debt(self):
        from instrument.commit_analysis import CommitAnalysis
        ca = CommitAnalysis(
            commit_hash="abc",
            sonar_available=True,
            sonar_bugs_delta=2,
            sonar_smells_delta=5,
        )
        dvs = compute_dvs(
            correctness=0.8,
            architectural_fit=0.7,
            convention_adherence=0.7,
            session_cost=0.10,
            commit_analysis=ca,
        )
        assert dvs.has_sonar is True
        assert dvs.technical_debt_introduced > 0

    def test_with_review(self):
        from instrument.review import CommitReview
        review = CommitReview(
            commit_hash="abc",
            reviewer_model="test",
            architectural_fit=0.85,
            convention_adherence=0.90,
            introduces_technical_debt=False,
            respects_existing_patterns=True,
            better_or_worse="better",
        )
        dvs = compute_dvs(
            correctness=0.9,
            architectural_fit=0.5,
            convention_adherence=0.5,
            session_cost=0.02,
            commit_review=review,
        )
        assert dvs.has_review is True
        assert dvs.architectural_fit == 0.85  # overridden by review

    def test_with_entropy(self):
        dvs = compute_dvs(
            correctness=0.9,
            architectural_fit=0.8,
            convention_adherence=0.8,
            session_cost=0.03,
            entropy_delta_value=0.5,
        )
        assert dvs.has_entropy is True
        assert dvs.future_cost_impact > 0


class TestStoryDVS:
    def test_averages_across_sessions(self):
        dvs = compute_story_dvs(
            session_costs=[0.01, 0.02, 0.03],
            correctness_values=[0.9, 0.8, 0.85],
            arch_fit_values=[0.8, 0.7, 0.75],
            convention_values=[0.85, 0.8, 0.82],
        )
        assert dvs.session_cost == 0.06  # summed
        assert dvs.score > 0

    def test_empty_sessions(self):
        dvs = compute_story_dvs([], [], [], [])
        assert dvs.verdict == "unavailable"


class TestEmojis:
    def test_verdict_to_emoji(self):
        assert "\u2191" in dvs_verdict_to_emoji("net_positive")
        assert "\u2193" in dvs_verdict_to_emoji("net_negative")
        assert "?" in dvs_verdict_to_emoji("unavailable")
