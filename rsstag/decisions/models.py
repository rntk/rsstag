"""Typed System One questions and answers shared by decisions providers."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class QuestionBase(BaseModel):
    instructions: JsonValue = None


class NoulQuestion(QuestionBase):
    type: Literal["noul"] = "noul"
    criteria: dict[Literal["true", "false"], JsonValue] | None = None


class ChoiceQuestion(QuestionBase):
    type: Literal["choice"] = "choice"
    criteria: dict[str, JsonValue] = Field(min_length=1, max_length=255)


class ScoreQuestion(QuestionBase):
    type: Literal["score"] = "score"
    criteria: list[JsonValue] = Field(min_length=1, max_length=10)


class BoxQuestion(QuestionBase):
    type: Literal["box"] = "box"


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion | BoxQuestion,
    Field(discriminator="type"),
]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: Probability


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: Probability
    probabilities: dict[str, Probability]


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float = Field(allow_inf_nan=False)
    confidence: Probability
    legend: dict[str, JsonValue]
    probabilities: dict[str, Probability]


class BoxCoordinates(BaseModel):
    top: Probability
    bottom: Probability
    left: Probability
    right: Probability


class BoxAnswer(BaseModel):
    type: Literal["box"]
    box: BoxCoordinates
    confidence: Probability | None


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer | BoxAnswer, Field(discriminator="type")
]


class Usage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class DecisionResponse(BaseModel):
    model: str
    answers: dict[str, Answer] = Field(min_length=1)
    usage: Usage


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1)
    state: str | dict[str, JsonValue] | list[JsonValue]
    questions: dict[str, Question] = Field(min_length=1)
    assets: dict[str, dict[str, JsonValue]] | None = None
