"""Provider-neutral decisions API, separate from generative LLM clients."""

from rsstag.decisions.client import (
    DecisionsClient,
    DecisionsError,
    Jev,
    LLamaCPPDecisions,
    create_decisions_client,
)
from rsstag.decisions.models import (
    BoxAnswer,
    BoxQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionResponse,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

__all__: list[str] = [
    "BoxAnswer",
    "BoxQuestion",
    "ChoiceAnswer",
    "ChoiceQuestion",
    "DecisionResponse",
    "DecisionsClient",
    "DecisionsError",
    "Jev",
    "LLamaCPPDecisions",
    "NoulAnswer",
    "NoulQuestion",
    "ScoreAnswer",
    "ScoreQuestion",
    "create_decisions_client",
]
