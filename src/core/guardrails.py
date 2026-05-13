"""Pluggable guardrails pipeline for content safety and security."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.core.logging import logger


class GuardrailAction(str, Enum):
    BLOCK = "block"
    FLAG = "flag"
    SANITIZE = "sanitize"
    ALLOW = "allow"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GuardrailResult:
    action: GuardrailAction = GuardrailAction.ALLOW
    severity: Severity = Severity.LOW
    message: str = ""
    sanitized: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseGuardrail(ABC):
    name: str = "base"

    @abstractmethod
    async def check(self, prompt: str, metadata: dict[str, Any]) -> GuardrailResult: ...


class PromptInjectionGuardrail(BaseGuardrail):
    name = "prompt_injection"

    _PATTERNS = [
        (
            r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|context)",
            Severity.CRITICAL,
            "Ignore previous instructions",
        ),
        (
            r"(?i)you\s+are\s+(now|no\s+longer)\s+(an?\s+)?(\w+\s+)?(assistant|ai|language\s+model|llm)",
            Severity.HIGH,
            "Role redefinition",
        ),
        (r"(?i)system\s*:\s*\n?", Severity.MEDIUM, "System prompt injection"),
        (r"(?i)\[INST\].*\[/INST\]", Severity.MEDIUM, "Instruction tokens"),
        (r"(?i)<\|im_start\|>.*<\|im_end\|>", Severity.MEDIUM, "ChatML injection"),
        (
            r"(?i)(DAN|developer\s+mode|jailbreak)\s+(mode|prompt)",
            Severity.CRITICAL,
            "Jailbreak attempt",
        ),
        (
            r"(?i)(pretend|act\s+as\s+if)\s+you\s+(are|were)\s+(an?\s+)?(evil|unethical|malicious|unfiltered)",
            Severity.CRITICAL,
            "Unethical role-reassignment",
        ),
    ]

    async def check(self, prompt: str, metadata: dict[str, Any]) -> GuardrailResult:
        for pattern, severity, label in self._PATTERNS:
            if re.search(pattern, prompt):
                logger.warning(
                    f"Guardrail [{self.name}]: {label} (severity={severity})"
                )
                if severity == Severity.CRITICAL:
                    return GuardrailResult(
                        action=GuardrailAction.BLOCK,
                        severity=severity,
                        message=f"Input blocked: {label}",
                    )
        return GuardrailResult(action=GuardrailAction.ALLOW)


class PIIGuardrail(BaseGuardrail):
    name = "pii_detection"

    _PATTERNS = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "US SSN"),
        (r"\b(?:\d[ -]*?){13,16}\b", "Credit card number"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email address"),
        (r"\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b", "Phone number"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP address"),
    ]

    async def check(self, prompt: str, metadata: dict[str, Any]) -> GuardrailResult:
        findings: list[str] = []
        sanitized = prompt
        for pattern, label in self._PATTERNS:
            if re.search(pattern, sanitized):
                findings.append(label)
                sanitized = re.sub(pattern, f"[REDACTED {label}]", sanitized)

        if findings:
            logger.info(f"Guardrail [{self.name}]: Redacted {', '.join(findings)}")
            return GuardrailResult(
                action=GuardrailAction.SANITIZE,
                severity=Severity.MEDIUM,
                message=f"PII detected and redacted: {', '.join(findings)}",
                sanitized=sanitized,
            )
        return GuardrailResult(action=GuardrailAction.ALLOW)


class ContentSafetyGuardrail(BaseGuardrail):
    name = "content_safety"

    _KEYWORDS = {
        "self_harm": [r"(?i)\b(suicide|kill\s+(myself|yourself)|self[- ]?harm)\b"],
        "violence": [r"(?i)\b(murder|torture|genocide|terroris[mt])\b"],
        "hate_speech": [r"(?i)\b(hate\s+speech|racial\s+slur)\b"],
    }

    async def check(self, prompt: str, metadata: dict[str, Any]) -> GuardrailResult:
        for category, patterns in self._KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, prompt):
                    logger.warning(f"Guardrail [{self.name}]: {category} detected")
                    return GuardrailResult(
                        action=GuardrailAction.FLAG,
                        severity=Severity.HIGH,
                        message=f"Content flagged: {category}",
                        metadata={"category": category},
                    )
        return GuardrailResult(action=GuardrailAction.ALLOW)


class GuardrailsPipeline:
    def __init__(self, guardrails: list[BaseGuardrail] | None = None):
        self._guardrails = guardrails or [
            PromptInjectionGuardrail(),
            PIIGuardrail(),
            ContentSafetyGuardrail(),
        ]

    def add_guardrail(self, guardrail: BaseGuardrail) -> None:
        self._guardrails.append(guardrail)

    def remove_guardrail(self, name: str) -> None:
        self._guardrails = [g for g in self._guardrails if g.name != name]

    @property
    def active_guardrails(self) -> list[str]:
        return [g.name for g in self._guardrails]

    async def run(
        self, prompt: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str, list[GuardrailResult]]:
        meta = metadata or {}
        results: list[GuardrailResult] = []
        current_prompt = prompt

        for guardrail in self._guardrails:
            result = await guardrail.check(current_prompt, meta)
            results.append({"name": guardrail.name, **result.__dict__})

            if result.action == GuardrailAction.BLOCK:
                logger.warning(f"Guardrail [{guardrail.name}] blocked request")
                break
            elif result.action == GuardrailAction.SANITIZE and result.sanitized:
                current_prompt = result.sanitized

        return current_prompt, results


_guardrails_pipeline: GuardrailsPipeline | None = None


def get_guardrails() -> GuardrailsPipeline:
    global _guardrails_pipeline
    if _guardrails_pipeline is None:
        _guardrails_pipeline = GuardrailsPipeline()
    return _guardrails_pipeline
