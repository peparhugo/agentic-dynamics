"""Constraint detection — measures whether the model notices missing constraints.

Scans the model's reasoning text for explicit mentions of constraints
that were deliberately removed from the prompt. This directly answers
the original research question: "R1 knows a constraint is missing and adds it."

Combined with recovery cost, it reveals whether detection drives recovery:
do models that detect constraints recover them more cheaply?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConstraintDetection:
    """Did the model detect a missing constraint?

    A constraint is "detected" if the model explicitly mentions it
    in its reasoning or generated code — either as a missing requirement,
    a design consideration, or an implemented feature.
    """

    constraint: str = ""
    detected: bool = False
    mentioned_in_reasoning: bool = False
    mentioned_in_code: bool = False
    detection_confidence: float = 0.0
    detection_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint": self.constraint,
            "detected": self.detected,
            "mentioned_in_reasoning": self.mentioned_in_reasoning,
            "mentioned_in_code": self.mentioned_in_code,
            "detection_confidence": round(self.detection_confidence, 4),
            "detection_evidence": self.detection_evidence[:3],
        }


@dataclass
class DetectionReport:
    """Complete constraint detection analysis for one experimental run."""

    operator: str = ""
    perturbation_class: str = ""
    strength: float = 0.0
    constraints_total: int = 0
    constraints_detected: int = 0
    detection_rate: float | None = None  # None when there are no constraints to detect
    detections: list[ConstraintDetection] = field(default_factory=list)

    # Recovery correlation
    recovery_cost_usd: float = 0.0
    recovery_tokens: int = 0
    correctness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "strength": self.strength,
            "constraints_total": self.constraints_total,
            "constraints_detected": self.constraints_detected,
            "detection_rate": (
                round(self.detection_rate, 4) if self.detection_rate is not None else None
            ),
            "detections": [d.to_dict() for d in self.detections],
            "recovery_cost_usd": round(self.recovery_cost_usd, 6),
            "recovery_tokens": self.recovery_tokens,
            "correctness": round(self.correctness, 4),
        }


def detect_constraints(
    final_response: str,
    constraints: list[str],
    *,
    code_files: dict[str, str] | None = None,
    operator: str = "",
    perturbation_class: str = "",
    strength: float = 0.0,
    recovery_cost_usd: float = 0.0,
    recovery_tokens: int = 0,
    correctness: float = 0.0,
) -> DetectionReport:
    """Scan both the model's closing text AND generated code for constraints.

    Two signal sources:
    1. Reasoning text: does the model explicitly MENTION the constraint?
    2. Generated code: did the model actually IMPLEMENT the constraint?

    The combination tells us whether the model silently implemented
    (DeepSeek's GRPO pattern — code without narration) or explicitly
    named but may not have implemented (Claude's pattern — narration
    without code on perturbed runs).
    """
    report = DetectionReport(
        operator=operator,
        perturbation_class=perturbation_class,
        strength=strength,
        constraints_total=len(constraints),
        recovery_cost_usd=recovery_cost_usd,
        recovery_tokens=recovery_tokens,
        correctness=correctness,
    )

    # Combine ALL text to search: closing response + all code files
    response_lower = final_response.lower()
    code_text = ""
    if code_files:
        code_text = " ".join(code_files.values()).lower()

    for constraint in constraints:
        keywords = _constraint_keywords(constraint)
        reasoning_evidence = []
        code_evidence = []

        for kw in keywords:
            # Check reasoning text
            if kw in response_lower:
                idx = response_lower.find(kw)
                context_start = max(0, idx - 200)
                context = response_lower[context_start:idx + len(kw) + 200]
                if not _is_code_context(context):
                    reasoning_evidence.append(kw)

            # Check actual code files
            if code_text and kw in code_text:
                code_evidence.append(kw)

        mentioned = len(reasoning_evidence) > 0
        implemented = len(code_evidence) > 0
        detected = mentioned or implemented

        if mentioned and implemented:
            confidence = 0.95  # both said and done
        elif implemented:
            confidence = 0.85  # silent implementation — DeepSeek's pattern
        elif mentioned:
            confidence = 0.4   # said but may not have done — Claude's pattern
        else:
            confidence = 0.0

        cd = ConstraintDetection(
            constraint=constraint,
            detected=detected,
            mentioned_in_reasoning=mentioned,
            mentioned_in_code=implemented,
            detection_confidence=confidence,
            detection_evidence=reasoning_evidence[:2] + code_evidence[:2],
        )
        report.detections.append(cd)
        if detected:
            report.constraints_detected += 1

    # None when there are no constraints to detect (a fabricated 0.0 would read "detected none
    # of none"); a rate over a real constraint set is measured, not defaulted.
    if report.constraints_total > 0:
        report.detection_rate = report.constraints_detected / report.constraints_total
    return report


def _constraint_keywords(constraint: str) -> list[str]:
    """Extract search keywords from a constraint description.

    Uses domain-specific keyword expansion to catch different phrasings
    of the same constraint (e.g., 'rate limiting' → 'rate_limit', 'ratelimit',
    'throttle', 'limiter').
    """
    constraint_lower = constraint.lower()

    # Domain-specific keyword expansions
    expansions = {
        # Python/web (existing)
        "jwt auth": ["jwt", "token", "authenticate", "bearer", "access_token", "refresh", "jsonwebtoken"],
        "refresh token": ["refresh", "refresh_token", "token_refresh"],
        "rate limit": ["rate_limit", "ratelimit", "ratelimit", "throttle", "limiter", "too many request", "429"],
        "input validation": ["validate", "validation", "sanitize", "schema", "marshmallow", "pydantic", "zod", "joi"],
        "paginated": ["paginate", "pagination", "page", "offset", "limit", "per_page", "cursor"],
        "error handling": ["error", "exception", "400", "404", "500", "abort", "http_error", "try", "catch"],
        "audit log": ["audit", "log", "logging", "logger", "trail"],
        "api version": ["version", "/v1/", "/v2/", "api_version", "versioning", "url_prefix"],

        # TypeScript/Node
        "websocket": ["websocket", "ws", "socket", "wss", "ws://"],
        "channel": ["channel", "subscribe", "unsubscribe", "publish", "broadcast", "room"],
        "cli": ["commander", "yargs", "argv", "process.argv", "cli", "command", "subcommand", "flag", "--", "option"],
        "frontmatter": ["frontmatter", "gray-matter", "yaml", "front matter", "frontmatter", "js-yaml"],
        "handlebars": ["handlebars", "hbs", "hbs", "template", "partial", "layout", "{{{", "compile"],
        "rss": ["rss", "feed", "atom", "xml", "pubdate"],
        "live reload": ["livereload", "live reload", "websocket", "chokidar", "watcher", "hot reload", "refresh", "inject"],
        "syntax highlighting": ["highlight", "hljs", "prism", "marked-highlight", "highlight.js", "code block"],
        "multi-tenant": ["tenant", "tenant_id", "multitenant", "multi-tenant", "workspace"],
        "prisma": ["prisma", "schema.prisma", "prisma schema"],
        "soft-delete": ["deleted_at", "soft delete", "soft_delete", "is_deleted"],
        "api key": ["api_key", "apikey", "x-api-key", "api key"],

        # Go
        "goroutine": ["goroutine", "go func", "go routine", "worker", "wg", "sync.wg"],
        "grpc": ["grpc", "proto", "protobuf", "protoc", ".proto", "bufconn"],
        "streaming": ["stream", "server_side_streaming", "bidirectional", "bidi"],
        "job queue": ["job", "queue", "enqueue", "dequeue", "worker", "dead letter"],
        "dead letter": ["dead", "dlq", "dead_letter", "dead-letter"],
        "heartbeat": ["heartbeat", "heart beat", "ping", "keepalive", "keep-alive"],
        "graceful shutdown": ["graceful", "shutdown", "sigint", "sigterm", "signal", "os.signal", "ctx.done"],
        "crawler": ["crawler", "spider", "fetch", "parse", "depth", "seed", "robots.txt", "robots"],

        # Rust
        "borrow check": ["borrow", "lifetime", "mut", "ref", "&self", "&mut"],
        "resp": ["resp", "redis", "serialization protocol", "$1", "*2", "+ok"],
        "tcp": ["tcp", "tcplistener", "tcpstream", "socket", "bind"],
        "aof": ["aof", "append", "append_only", "append-only", "replay", "log file"],
        "tokio": ["tokio", "async", "await", "spawn", "runtime"],
        "ttl": ["ttl", "expire", "expiration", "expiry", "duration", "instant"],
        "proxy": ["proxy", "reverse proxy", "upstream", "backend", "load balancer", "round robin"],
        "cache": ["cache", "lru", "caching", "ttl", "eviction", "invalidate"],
        "health check": ["health", "healthcheck", "health_check", "/health", "alive"],
        "git object": ["git", "sha1", "sha256", "blob", "tree", "commit", "hash", "deflate", "zlib", "object"],
        "content-addressable": ["content", "addressable", "hash", "sha", "store"],

        # General
        "test": ["test", "test", "spec", "pytest", "vitest", "jest", "mocha", "assert", "expect", "describe", "it("],
        "config": ["config", "configuration", "settings", "env", "toml", "yaml"],
        "logging": ["log", "logging", "winston", "pino", "slog", "tracing", "logger"],
    }

    keywords = set()
    for pattern, terms in expansions.items():
        if pattern in constraint_lower:
            keywords.update(terms)

    # Also add individual words from the constraint (fallback)
    stop = {"must", "the", "a", "an", "be", "with", "for", "and", "or", "in", "on", "to",
            "is", "of", "all", "that", "this", "has", "have", "should", "can", "will",
            "at", "by", "from", "no", "not", "but", "if", "so"}
    words = constraint_lower.split()
    for w in words:
        if w not in stop and len(w) > 2:
            keywords.add(w)

    return list(keywords)[:12]


def _is_code_context(text: str) -> bool:
    """Heuristic: is this text segment code rather than prose?"""
    code_indicators = [
        "def ", "class ", "import ", "from ", "return ", "```", "self.",
        "@app", "@route", "endpoint", "func ", "const ", "let ",
        "curl", "GET ", "POST ", "PUT ", "DELETE ",
    ]
    return any(ci in text for ci in code_indicators)


def detection_summary(detections: list[DetectionReport]) -> str:
    """Generate a markdown summary table of constraint detection results."""
    lines = [
        "| Operator | Class | Detected | Detection Rate | Recovery $ | Recovery Tok | Correctness |",
        "|----------|-------|----------|---------------|------------|-------------|-------------|",
    ]
    for d in detections:
        lines.append(
            f"| {d.operator} | {d.perturbation_class} | "
            f"{d.constraints_detected}/{d.constraints_total} | "
            f"{d.detection_rate:.0%} | "
            f"${d.recovery_cost_usd:.4f} | "
            f"{d.recovery_tokens:,} | "
            f"{d.correctness:.0%} |"
        )
    return "\n".join(lines)
