"""
Harness — orchestrator that chains all guardrails into a single pipeline.

Flow:
  1. SecurityGuardrail.check(input)    — pre-input jailbreak detection
  2. DomainClassifier.classify(input)  — intent classification
  3. Harness.decide()                   — determine action (block, redirect, pass)
  4. (if PASS) → agent processes input → response
  5. ContentGuardrail.scan(response)   — post-output data leak detection
  6. (if unclean) → sanitize response
  7. Return HarnessResult with all guardrail results and final action
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .schemas import (
    ContentResult,
    DomainResult,
    DomainType,
    HarnessAction,
    HarnessResult,
    SecurityResult,
    ThreatLevel,
)
from .content_guardrail import ContentGuardrail
from .domain_classifier import DomainClassifier
from .security_guardrail import SecurityGuardrail

logger = logging.getLogger(__name__)


class Harness:
    """Orchestrates all guardrails for the support agent.

    Provides a single entry point for processing user input through
    the full guardrail pipeline, and optionally scanning agent output.

    Usage:
        harness = Harness()
        result = harness.process_input(user_message)
        if result.action == HarnessAction.PASS:
            response = agent.process(result.safe_input)
            final = harness.process_output(response, result)
    """

    def __init__(
        self,
        security_guardrail: Optional[SecurityGuardrail] = None,
        domain_classifier: Optional[DomainClassifier] = None,
        content_guardrail: Optional[ContentGuardrail] = None,
        block_on_high_security: bool = True,
        block_personal_tasks: bool = True,
        redirect_out_of_domain: bool = True,
        domain_redirect_message: Optional[str] = None,
        personal_task_block_message: Optional[str] = None,
        security_block_message: Optional[str] = None,
    ) -> None:
        """Initialize the harness with configurable guardrails.

        Args:
            security_guardrail: Custom SecurityGuardrail instance. Created if None.
            domain_classifier: Custom DomainClassifier instance. Created if None.
            content_guardrail: Custom ContentGuardrail instance. Created if None.
            block_on_high_security: If True, HIGH security threats also block. Default True.
            block_personal_tasks: If True, personal tasks are blocked. Default True.
            redirect_out_of_domain: If True, out-of-domain queries are redirected. Default True.
            domain_redirect_message: Custom message for domain redirection.
            personal_task_block_message: Custom message for task blocking.
            security_block_message: Custom message for security blocking.
        """
        self._security = security_guardrail or SecurityGuardrail(block_on_high=block_on_high_security)
        self._domain = domain_classifier or DomainClassifier()
        self._content = content_guardrail or ContentGuardrail(sanitize=True)
        self._block_personal_tasks = block_personal_tasks
        self._redirect_out_of_domain = redirect_out_of_domain

        # Default messages
        self._domain_redirect_msg = domain_redirect_message or (
            "Soy un asistente especializado en operaciones de Brasaland. "
            "Mi función es ayudarte con temas relacionados con la gestión del restaurante, "
            "inventario, incidencias, proveedores, turnos y planificación. "
            "¿Hay algo relacionado con Brasaland en lo que pueda ayudarte?"
        )
        self._personal_task_block_msg = personal_task_block_message or (
            "Lo siento, no puedo ayudarte con tareas personales o ajenas a Brasaland. "
            "Mi función es exclusivamente la gestión operativa del restaurante. "
            "¿Hay algo relacionado con Brasaland en lo que pueda ayudarte?"
        )
        self._security_block_msg = security_block_message or (
            "No puedo procesar esa solicitud. Por favor, mantén la conversación "
            "dentro del contexto de operaciones de Brasaland."
        )

        logger.info(
            "Harness initialized (block_personal=%s, redirect_out=%s, block_high_sec=%s)",
            block_personal_tasks, redirect_out_of_domain, block_on_high_security,
        )

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def process_input(self, text: str) -> HarnessResult:
        """Run the full pre-input guardrail pipeline.

        Steps:
          1. Security check (jailbreak / prompt injection)
          2. Domain classification (intent detection)
          3. Decision (block, redirect, or pass)

        Args:
            text: The user's input message.

        Returns:
            HarnessResult with the determined action and all guardrail results.
        """
        start_time = time.monotonic()

        if not text or not text.strip():
            return self._make_result(
                action=HarnessAction.PASS,
                domain_result=DomainResult(
                    domain=DomainType.SMALL_TALK,
                    confidence=1.0,
                    explanation="Empty input, treating as small talk.",
                ),
                safe_input=text,
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

        # Step 1: Security check
        security = self._security.check(text)
        guardrail_results: dict[str, object] = {"security": security}

        # Step 2: Domain classification (always run, even on security block)
        domain = self._domain.classify(text)
        guardrail_results["domain"] = domain

        if self._security.should_block(security):
            logger.info(
                "Security block: threat=%s, confidence=%.2f",
                security.threat, security.confidence,
            )
            return self._make_result(
                action=HarnessAction.BLOCK,
                security_result=security,
                domain_result=domain,
                guardrail_results=guardrail_results,
                safe_input=self._security_block_msg,
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

        # Step 2a: Personal task → block
        if domain.domain == DomainType.PERSONAL_TASK and self._block_personal_tasks:
            logger.info(
                "Personal task blocked: domain=%s, confidence=%.2f",
                domain.domain, domain.confidence,
            )
            return self._make_result(
                action=HarnessAction.BLOCK,
                security_result=security,
                domain_result=domain,
                guardrail_results=guardrail_results,
                safe_input=self._personal_task_block_msg,
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

        # Step 2b: Out-of-domain (trivia, small-talk, sensitive query) → redirect
        if domain.domain in (
            DomainType.TRIVIA,
            DomainType.SMALL_TALK,
            DomainType.SENSITIVE_QUERY,
        ) and self._redirect_out_of_domain:
            logger.info(
                "Out-of-domain redirect: domain=%s, confidence=%.2f",
                domain.domain, domain.confidence,
            )
            return self._make_result(
                action=HarnessAction.REDIRECT,
                security_result=security,
                domain_result=domain,
                guardrail_results=guardrail_results,
                safe_input=self._domain_redirect_msg,
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

        # Step 3: PASS — forward to agent
        return self._make_result(
            action=HarnessAction.PASS,
            security_result=security,
            domain_result=domain,
            guardrail_results=guardrail_results,
            safe_input=text,
            processing_time_ms=(time.monotonic() - start_time) * 1000,
        )

    def process_output(self, response: str, input_result: HarnessResult) -> HarnessResult:
        """Run the post-output guardrail pipeline.

        Scans the agent's response for sensitive data leakage and
        optionally sanitizes it.

        Args:
            response: The agent's generated response.
            input_result: The HarnessResult from process_input (mutated in place).

        Returns:
            The updated HarnessResult with content scan results.
        """
        content = self._content.scan(response)

        # Add content result to guardrail_results
        input_result.guardrail_results["content"] = content
        input_result.content_result = content

        if content.is_clean:
            input_result.action = HarnessAction.PASS
            input_result.safe_response = response
        else:
            input_result.action = HarnessAction.SANITIZE
            input_result.safe_response = content.sanitized_response or response
            logger.info(
                "Content sanitized: %.2f confidence, %d pattern group(s) matched",
                content.confidence,
                len(content.matched_patterns or []),
            )

        return input_result

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _make_result(
        self,
        action: HarnessAction,
        security_result: Optional[SecurityResult] = None,
        domain_result: Optional[DomainResult] = None,
        guardrail_results: Optional[dict[str, object]] = None,
        safe_input: Optional[str] = None,
        processing_time_ms: float = 0.0,
    ) -> HarnessResult:
        """Build a HarnessResult from the given components."""
        return HarnessResult(
            action=action,
            security_result=security_result,
            domain_result=domain_result,
            guardrail_results=guardrail_results or {},
            safe_input=safe_input,
            processing_time_ms=processing_time_ms,
        )