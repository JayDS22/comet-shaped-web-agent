"""One fully-implemented task against a local fixture.

Additional tasks (pagination extract, checkout-with-permission-gate, paper
search, CAPTCHA-graceful-fail) are documented in the README roadmap and
will land as they're implemented, not before. Shipping four empty stubs
in this file made the harness look aspirational rather than working.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from agent.loop import RunResult
from tasks.fixtures.serve import BASE_URL


@dataclass
class TaskSpec:
    id: str
    title: str
    prompt: str
    start_url: str
    expected_answer: Optional[str] = None
    max_steps: int = 8
    allow_ask: bool = True


TASKS: list[TaskSpec] = [
    TaskSpec(
        id="T1_form_fill",
        title="Fill a search form and extract the first result URL",
        prompt=(
            f"Go to {BASE_URL}. Read the page. There is a search form with a text "
            f"input named 'q' and a submit button. Fill the input with the value "
            f"'perplexity', then click the submit button. Read the resulting page. "
            f"The page has three result links. Return the URL of the FIRST result "
            f"via finish(answer=<url>)."
        ),
        start_url=BASE_URL,
        expected_answer="perplexity.ai",
        max_steps=6,
        allow_ask=True,
    ),
]


def get(task_id: str) -> Optional[TaskSpec]:
    return next((t for t in TASKS if t.id == task_id), None)
