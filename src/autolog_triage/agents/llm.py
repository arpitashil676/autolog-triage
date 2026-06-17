"""LLM provider abstraction.

The agents depend on an :class:`LLMProvider` interface rather than any
concrete SDK. Two implementations are shipped:

* :class:`MockLLMProvider` -- deterministic, offline, no API key. It returns
  rule-derived JSON so the *entire* pipeline, test-suite and evaluation run
  reproducibly in CI. This is the default.
* :class:`AnthropicLLMProvider` -- calls a real model when an API key and the
  optional ``anthropic`` dependency are present.

Selection is via :func:`get_provider`, driven by environment variables, so
switching backends never requires touching agent code.
"""

from __future__ import annotations

import json
import os
from typing import Protocol


class LLMProvider(Protocol):
    """Minimal interface the agents rely on."""

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover - protocol
        ...


class MockLLMProvider:
    """Deterministic offline provider.

    It does not "understand" the prompt; instead the agents pass structured
    context and ask for JSON, and this mock echoes a sensible, rule-derived
    JSON object. That keeps the data contract identical to the real provider
    while remaining fully reproducible.
    """

    name = "mock"

    def complete(self, system: str, prompt: str) -> str:
        # The agents embed a JSON block under a marker we can echo back.
        # For triage prompts we synthesize a plausible structured answer.
        if "ANALYZE_FINDING" in prompt:
            return self._mock_triage(prompt)
        if "SUMMARIZE_RUN" in prompt:
            return self._mock_summary(prompt)
        return "{}"

    @staticmethod
    def _extract(prompt: str, key: str, default: str = "") -> str:
        marker = f"<{key}>"
        end = f"</{key}>"
        if marker in prompt and end in prompt:
            return prompt.split(marker, 1)[1].split(end, 1)[0].strip()
        return default

    def _mock_triage(self, prompt: str) -> str:
        category = self._extract(prompt, "category", "unknown")
        component = self._extract(prompt, "component", "Unknown")
        causes = {
            "crash": f"Unhandled exception or memory fault in {component}.",
            "timeout": f"{component} dependency unresponsive or deadlock.",
            "assertion": f"{component} reached an invalid state precondition.",
            "anomalous_latency": f"{component} resource contention or slow I/O.",
            "unknown": "Insufficient signal to determine a specific cause.",
        }
        actions = {
            "crash": "Capture core dump; retest in isolation; file blocking defect.",
            "timeout": "Increase trace verbosity on the dependency; check deadlines.",
            "assertion": "Review state machine and preconditions around the assert.",
            "anomalous_latency": "Profile the component; compare against latency budget.",
            "unknown": "Re-run with debug logging to gather more evidence.",
        }
        fp = category == "unknown"
        return json.dumps(
            {
                "probable_root_cause": causes.get(category, causes["unknown"]),
                "recommended_action": actions.get(category, actions["unknown"]),
                "is_likely_false_positive": fp,
                "rationale": f"Categorized as '{category}' for {component} from log evidence.",
            }
        )

    def _mock_summary(self, prompt: str) -> str:
        n = self._extract(prompt, "n_findings", "0")
        crit = self._extract(prompt, "n_critical", "0")
        return json.dumps(
            {
                "summary": (
                    f"Run analysis complete: {n} finding(s), {crit} critical. "
                    "Critical and error findings should be triaged first; "
                    "see the table below for per-finding root cause and actions."
                )
            }
        )


class AnthropicLLMProvider:
    """Real provider backed by the Anthropic Messages API.

    Imported lazily so the package works without the optional dependency.
    """

    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 1024) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "anthropic package not installed. Install with: pip install 'autolog-triage[llm]'"
            ) from exc
        from anthropic import Anthropic

        self._client = Anthropic()  # reads ANTHROPIC_API_KEY from env
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover - needs network
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts)


def get_provider() -> LLMProvider:
    """Return a provider based on environment configuration.

    ``AUTOLOG_LLM=anthropic`` selects the real backend (requires the optional
    dependency and ``ANTHROPIC_API_KEY``). Anything else -- including the
    default unset case -- selects the deterministic mock.
    """
    choice = os.environ.get("AUTOLOG_LLM", "mock").lower()
    if choice == "anthropic":
        return AnthropicLLMProvider(model=os.environ.get("AUTOLOG_MODEL", "claude-sonnet-4-6"))
    return MockLLMProvider()
