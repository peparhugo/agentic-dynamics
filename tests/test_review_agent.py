"""Tests for agent review system."""

import json

import pytest
pytestmark = pytest.mark.fast

from agentic_dynamics.reporting.review import (
    CommitReview,
    StoryReview,
    _parse_commit_review,
    _parse_story_review,
)


class TestCommitReview:
    def test_serialization(self):
        review = CommitReview(
            commit_hash="abc123",
            reviewer_model="openai/gpt-5.6",
            architectural_fit=0.8,
            convention_adherence=0.9,
            introduces_technical_debt=False,
            respects_existing_patterns=True,
            better_or_worse="better",
            problems=[],
            strengths=["Clean abstraction", "Good naming"],
            summary="Well-structured commit.",
        )
        d = review.to_dict()
        assert d["architectural_fit"] == 0.8
        assert d["better_or_worse"] == "better"

    def test_from_dict(self):
        d = {
            "commit_hash": "def456",
            "reviewer_model": "test",
            "architectural_fit": 0.6,
            "convention_adherence": 0.7,
            "introduces_technical_debt": True,
            "respects_existing_patterns": False,
            "better_or_worse": "worse",
            "problems": ["Circular import"],
            "strengths": [],
            "summary": "Needs work.",
        }
        review = CommitReview.from_dict(d)
        assert review.architectural_fit == 0.6
        assert len(review.problems) == 1
        assert review.problems[0].description == "Circular import"
        assert review.problems[0].category == "other"  # backward compat: string → other

    def test_from_dict_structured_problems(self):
        """Test that structured problem dicts are parsed correctly."""
        d = {
            "commit_hash": "ghi789",
            "reviewer_model": "test",
            "architectural_fit": 0.5,
            "convention_adherence": 0.6,
            "introduces_technical_debt": False,
            "respects_existing_patterns": True,
            "better_or_worse": "neutral",
            "problems": [
                {"category": "testing", "severity": "major", "description": "No edge case tests"},
                {"category": "convention", "severity": "minor", "description": "Missing type hints"},
            ],
            "strengths": ["Clean architecture"],
            "summary": "OK.",
        }
        review = CommitReview.from_dict(d)
        assert len(review.problems) == 2
        assert review.problems[0].category == "testing"
        assert review.problems[0].severity == "major"
        assert review.problems[1].category == "convention"
        assert review.problems[1].severity == "minor"


class TestStoryReview:
    def test_serialization(self):
        review = StoryReview(
            story_name="task_manager",
            reviewer_model="anthropic/claude-fable-5",
            overall_coherence=0.75,
            compounding_issues=["Auth decision constrained pagination"],
            key_decisions=["Repository pattern refactor was clean"],
            trajectory_description="Quality improved across sessions.",
            summary="Coherent story with one architectural trade-off.",
        )
        d = review.to_dict()
        assert d["overall_coherence"] == 0.75
        assert len(d["compounding_issues"]) == 1


class TestParseCommitReview:
    def test_parses_valid_json(self):
        response = json.dumps({
            "architectural_fit": 0.9,
            "convention_adherence": 0.85,
            "introduces_technical_debt": False,
            "respects_existing_patterns": True,
            "better_or_worse": "better",
            "problems": [],
            "strengths": ["Good use of existing patterns"],
            "summary": "Solid commit.",
        })
        review = _parse_commit_review(response, "abc123", "test-model")
        assert review.architectural_fit == 0.9
        assert review.better_or_worse == "better"

    def test_parses_json_with_surrounding_text(self):
        response = "Here is the review:\n" + json.dumps({
            "architectural_fit": 0.3,
            "convention_adherence": 0.4,
            "introduces_technical_debt": True,
            "respects_existing_patterns": False,
            "better_or_worse": "worse",
            "problems": ["God module created"],
            "strengths": [],
            "summary": "Bad commit.",
        }) + "\nEnd of review."
        review = _parse_commit_review(response, "abc123", "test-model")
        assert review.architectural_fit == 0.3
        assert review.introduces_technical_debt is True

    def test_falls_back_on_garbage(self):
        review = _parse_commit_review("not json at all", "abc123", "test-model")
        assert review.commit_hash == "abc123"
        assert review.architectural_fit == 0.5  # default
        assert review.better_or_worse == "unclear"

    def test_falls_back_on_none(self):
        review = _parse_commit_review(None, "abc123", "test-model")
        assert review.architectural_fit == 0.5


class TestParseStoryReview:
    def test_parses_valid_json(self):
        response = json.dumps({
            "overall_coherence": 0.8,
            "compounding_issues": [],
            "key_decisions": ["Auth middleware was well-placed"],
            "trajectory_description": "Steady improvement.",
            "summary": "Good story.",
        })
        review = _parse_story_review(response, "test_story", "claude")
        assert review.overall_coherence == 0.8
        assert review.summary == "Good story."

    def test_falls_back_on_none(self):
        review = _parse_story_review(None, "test_story", "claude")
        assert review.overall_coherence == 0.5
