"""Two fully-implemented tasks: one on a local fixture, one on a bot-friendly real site.

T3-T5 remain roadmap items (see README) and are not stubbed in code.
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
    TaskSpec(
        id="T2_pagination_extract",
        title="Walk pagination on quotes.toscrape.com, extract authors from 2 pages",
        prompt=(
            "Go to https://quotes.toscrape.com/. Read the page. Note the authors "
            "listed on page 1. Then navigate to https://quotes.toscrape.com/page/2/ "
            "and read that page. Note the authors on page 2. "
            "Return a comma-separated list of ALL unique author names you observed "
            "across both pages via finish(answer=<comma-separated names>). "
            "Do not invent authors - only include those you actually saw."
        ),
        start_url="https://quotes.toscrape.com/",
        expected_answer="Einstein",  # every page 1 has an Einstein quote
        max_steps=8,
        allow_ask=True,
    ),
]


def get(task_id: str) -> Optional[TaskSpec]:
    return next((t for t in TASKS if t.id == task_id), None)
