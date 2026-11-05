"""Summary tree judgments through the decisions API, and their LLM fallbacks."""

import json
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from rsstag.decisions.client import DecisionsClient, DecisionsError
from rsstag.decisions.models import DecisionResponse, Question
from rsstag.summary_tree.judge import SummaryJudge, build_judge
from rsstag.summary_tree.model import TOPIC, Segment, add_node, build_post_nodes
from rsstag.summary_tree.pipeline import SummaryTreePipeline
from rsstag.summary_tree.screening import (
    IRRELEVANT,
    RELEVANT,
    UNCERTAIN,
    decide,
    screen_posts,
)
from rsstag.summary_tree.sources import SourcePost
from rsstag.summary_tree.topics import TopicBuilder, decode_titles
from rsstag.summary_tree.verify import ClaimVerifier
from tests.test_summary_tree_pipeline import FakeRouter


def _noul(p: float) -> Dict[str, Any]:
    return {"type": "noul", "noul": p}


class FakeClient(DecisionsClient):
    """Passages mentioning 'apple' are relevant; topics match the digest's first word."""

    def __init__(self, fail: bool = False) -> None:
        super().__init__("http://fake", "fake-model")
        self.fail: bool = fail
        self.requests: List[Dict[str, Any]] = []

    def call(self, state: Any, questions: Any, **_kwargs: Any) -> DecisionResponse:
        self.requests.append({"state": state, "questions": questions})
        if self.fail:
            raise DecisionsError("down")
        answers: Dict[str, Any] = {name: self._answer(state, name, q) for name, q in questions.items()}
        return DecisionResponse.model_validate(
            {"model": self.model, "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}})

    @staticmethod
    def _answer(state: Dict[str, Any], name: str, question: Question) -> Dict[str, Any]:
        if name == "about":
            texts: str = " ".join(state["post"]["passages"].values())
            return _noul(0.9 if "apple" in texts else 0.05)
        if name.startswith("p"):
            return _noul(0.9 if "apple" in state["post"]["passages"][name] else 0.05)
        if name.startswith("fits_"):
            return _noul(0.05 if "Weather" in str(question.instructions) else 0.9)
        if name.startswith("topic_"):
            options: List[str] = list(question.criteria)
            digest: str = str(question.instructions).split("Summary: ", 1)[1]
            pick: str = next((o for o in options if digest.startswith(o)), options[0])
            return {"type": "choice", "choice": pick, "confidence": 0.9,
                    "probabilities": {o: (0.9 if o == pick else 0.1 / (len(options) - 1)) for o in options}}
        claim: str = state["claims"][name]["claim"]
        return _noul(0.05 if "invented" in claim else 0.9)


def _judge(fail: bool = False) -> SummaryJudge:
    db: MagicMock = MagicMock()
    db.__getitem__.return_value.find_one.return_value = None
    return SummaryJudge(db, FakeClient(fail), "u", workers=4, retry_delay=0)


class TestScreeningTruthTable(unittest.TestCase):
    passages: List[str] = ["Title", "a", "b"]

    def _answers(self, about: float, rows: Dict[int, float]) -> List[Any]:
        return [{"about": MagicMock(type="noul", noul=about),
                 **{f"p{r}": MagicMock(type="noul", noul=p) for r, p in rows.items()}}]

    def test_relevant_keeps_title_and_plausible_passages(self) -> None:
        screen = decide(self._answers(0.9, {1: 0.1, 2: 0.8, 3: 0.2}), self.passages)
        self.assertEqual((screen.verdict, screen.rows), (RELEVANT, [1, 2]))

    def test_irrelevant_when_post_and_passages_say_no(self) -> None:
        screen = decide(self._answers(0.1, {1: 0.1, 2: 0.2, 3: 0.0}), self.passages)
        self.assertEqual((screen.verdict, screen.rows), (IRRELEVANT, []))

    def test_unsettled_or_failed_keeps_everything(self) -> None:
        self.assertEqual(decide(self._answers(0.5, {2: 0.4}), self.passages).verdict, UNCERTAIN)
        failed = decide([None], self.passages)
        self.assertEqual((failed.verdict, failed.rows), (UNCERTAIN, [1, 2, 3]))

    def test_screen_posts_selects_passages(self) -> None:
        post: SourcePost = SourcePost("1", "News", "Pears are fine. The apple crop grew. Rain fell.", "f", "", 1)
        evidence: Dict[str, List[str]] = {"1": ["News", "Pears are fine.", "The apple crop grew.", "Rain fell."]}
        screens = screen_posts(_judge(), "apple", [post], evidence)
        self.assertEqual((screens["1"].verdict, screens["1"].rows), (RELEVANT, [1, 3]))


class TestJudge(unittest.TestCase):
    def test_failure_disables_judge_and_is_not_an_answer(self) -> None:
        judge: SummaryJudge = _judge(fail=True)
        self.assertEqual(judge.ask_many([({"x": 1}, {})] * 3), [None, None, None])
        self.assertFalse(judge.active)
        self.assertEqual(judge.failures, 2)  # one retry, then off for the run

    def test_build_judge_is_opt_in(self) -> None:
        config: Dict[str, Any] = {"decisions": {"provider": "llamacpp"},
                                  "llamacpp_decisions": {"host": "http://localhost:8080"}}
        self.assertIsNone(build_judge(MagicMock(), config, "u"))
        config["decisions"]["summary_tree"] = "on"
        self.assertIsInstance(build_judge(MagicMock(), config, "u"), SummaryJudge)


class TestTopicsWithJudge(unittest.TestCase):
    def _nodes(self, titles: List[str]) -> Any:
        posts: List[SourcePost] = [SourcePost(str(i), t, "t", "f", "", i) for i, t in enumerate(titles)]
        post_nodes, nodes, _ = build_post_nodes(posts)
        for node in nodes.values():
            node.segments = [Segment(node.title + " news.", [{"kind": "rows", "first": 1, "last": 1}])]
        return [post_nodes[p.pid] for p in posts], nodes

    def test_decode_titles(self) -> None:
        raw: str = json.dumps({"topics": [{"title": "Prices", "description": "Price moves"},
                                          {"title": "Other"}, {"title": "Harvest"}]})
        self.assertEqual(decode_titles(raw), {"Prices": "Price moves", "Harvest": "Harvest"})
        self.assertIsNone(decode_titles(json.dumps({"topics": [{"title": "Only"}]})))

    def test_llm_proposes_judge_assigns(self) -> None:
        ids, nodes = self._nodes(["Prices up", "Harvest late", "Prices down", "Weather", "Harvest early"])
        llm: MagicMock = MagicMock()

        def ask(prompt: str, accept: Any) -> str:
            raw: str = json.dumps({"topics": [{"title": "Prices", "description": "Price moves"},
                                              {"title": "Harvest", "description": "Crop timing"}]})
            accept(raw)
            return raw

        llm.ask.side_effect = ask
        groups = TopicBuilder(llm, "apple", nodes, MagicMock(), _judge()).split(ids, ["apple"])
        self.assertEqual(groups, [("Prices", [ids[0], ids[2]]), ("Harvest", [ids[1], ids[4]]),
                                  ("Other", [ids[3]])])
        self.assertTrue(llm.ask.call_args.args[0].startswith("TASK: PROPOSE SUB-TOPICS"))


class TestVerifier(unittest.TestCase):
    def test_drops_unsupported_claims_and_rejects_empty_posts(self) -> None:
        post_nodes, nodes, evidence = build_post_nodes([SourcePost("1", "T", "Apple crop grew.", "f", "", 1)])
        node_id: str = post_nodes["1"]
        rows: List[Dict[str, Any]] = [{"kind": "rows", "first": 2, "last": 2}]
        verifier: ClaimVerifier = ClaimVerifier(_judge(), "apple", nodes, evidence)
        mixed = verifier.filter("post", {node_id: [Segment("The crop grew", rows), Segment(" and",),
                                                   Segment(" an invented claim.", rows)]})
        self.assertEqual([s.text for s in mixed[node_id] or []], ["The crop grew"])
        bad = verifier.filter("post", {node_id: [Segment("An invented claim.", rows)]})
        self.assertIsNone(bad[node_id])
        self.assertEqual(verifier.filter("overview", {node_id: [Segment("An invented claim.", rows)]})[node_id][0].text,
                         "An invented claim.")

    def test_all_dropped_detail_claim_rejects_answer(self) -> None:
        post_nodes, nodes, evidence = build_post_nodes(
            [SourcePost("1", "T", "Apple crop grew.", "f", "", 1)])
        post_id: str = post_nodes["1"]
        nodes[post_id].segments = [Segment("Apple crop grew", [{"kind": "rows", "first": 2, "last": 2}])]
        topic_id: str = add_node(nodes, TOPIC, "Harvest", [post_id], path=["apple", "Harvest"])
        claim: List[Dict[str, Any]] = [{"kind": "claim", "child": post_id, "segment": 0}]
        verifier: ClaimVerifier = ClaimVerifier(_judge(), "apple", nodes, evidence)
        rejected = verifier.filter("detail", {topic_id: [Segment("An invented claim.", claim)]})
        self.assertIsNone(rejected[topic_id])


class TestPipelineWithJudge(unittest.TestCase):
    def _run(self, judge: SummaryJudge, posts: List[SourcePost], limit: int = 10) -> Any:
        router: FakeRouter = FakeRouter()
        with patch("rsstag.summary_tree.pipeline.RssTagSummaryTrees") as store_cls, patch(
            "rsstag.summary_tree.pipeline.load_posts", return_value=posts
        ) as load, patch("rsstag.summary_tree.pipeline.SummaryLLM._cached", return_value=None), patch(
            "rsstag.summary_tree.pipeline.SummaryLLM._store"
        ), patch("rsstag.summary_tree.pipeline.prepare_cache"):
            store = store_cls.return_value
            store.set_stage.return_value = store.set_progress.return_value = True
            store.save_result.return_value = True
            ok: bool = SummaryTreePipeline(MagicMock(), router, "u", judge=judge).run(
                {"_id": "t1", "run_id": "r", "filters": {"entity": "apple"}, "options": {"limit": limit}})
        self.assertTrue(ok)
        return store.save_result.call_args.args[3], router, load

    def test_screened_out_posts_cost_no_generation(self) -> None:
        posts: List[SourcePost] = [SourcePost("1", "Apple prices", "apple up", "f", "", 1),
                                   SourcePost("2", "Pears", "pear news", "f", "", 2),
                                   SourcePost("3", "Apple harvest", "apple late", "f", "", 3)]
        result, router, load = self._run(_judge(), posts, limit=2)
        self.assertEqual(load.call_args.args[3]["limit"], 6)  # screens more candidates
        self.assertEqual([p["pid"] for p in result["posts"]], ["1", "3"])
        self.assertEqual([(p["pid"], p["reason"]) for p in result["skipped"]], [("2", "irrelevant")])
        self.assertFalse(any('"Pears"' in prompt for prompt in router.prompts))
        self.assertEqual(result["metrics"]["screened_out"], 1)

    def test_judge_outage_falls_back_to_llm(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), t, "t", "f", "", i) for i, t in
                                   enumerate(["Prices rise", "Prices fall", "Harvest", "Unrelated",
                                              "Prices hold", "Harvest late"], 1)]
        result, _, _ = self._run(_judge(fail=True), posts)
        self.assertEqual(result["metrics"]["topics"], 2)
        self.assertFalse(result["metrics"]["decisions_active"])
        self.assertEqual(result["metrics"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
