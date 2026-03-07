import unittest

from rsstag.entity_extractor import RssTagEntityExtractor


class DummyLLM:
    def __init__(self, response: str):
        self._response = response

    def call(self, user_msgs, temperature=0.0):
        return self._response


class TestEntityExtractorLLMFilter(unittest.TestCase):
    def test_llm_filter_accepts_only_ids_subset(self):
        ex = RssTagEntityExtractor()
        candidates = [
            {
                "raw_text": "Apple",
                "norm_text": "appl",
                "raw": ["Apple"],
                "norm": ["appl"],
                "ctx_left": "",
                "ctx_right": "",
            },
            {
                "raw_text": "Monday",
                "norm_text": "monday",
                "raw": ["Monday"],
                "norm": ["monday"],
                "ctx_left": "",
                "ctx_right": "",
            },
            {
                "raw_text": "Microsoft",
                "norm_text": "microsoft",
                "raw": ["Microsoft"],
                "norm": ["microsoft"],
                "ctx_left": "",
                "ctx_right": "",
            },
        ]

        llm = DummyLLM('{"keep":[0,2]}')
        kept = ex.llm_filter_candidates(candidates, llm, max_candidates=10)
        self.assertEqual(set(c["raw_text"] for c in kept), {"Apple", "Microsoft"})

    def test_llm_filter_ignores_hallucinated_ids_and_falls_back(self):
        ex = RssTagEntityExtractor()
        candidates = [
            {
                "raw_text": "Apple",
                "norm_text": "appl",
                "raw": ["Apple"],
                "norm": ["appl"],
                "ctx_left": "",
                "ctx_right": "",
            },
            {
                "raw_text": "Monday",
                "norm_text": "monday",
                "raw": ["Monday"],
                "norm": ["monday"],
                "ctx_left": "",
                "ctx_right": "",
            },
        ]

        # 999 is out of range => no valid ids => should not filter (return original candidates)
        llm = DummyLLM('{"keep":[999]}')
        kept = ex.llm_filter_candidates(candidates, llm, max_candidates=10)
        self.assertEqual([c["raw_text"] for c in kept], ["Apple", "Monday"])

    def test_llm_filter_parses_code_fences(self):
        ex = RssTagEntityExtractor()
        candidates = [
            {
                "raw_text": "Paris",
                "norm_text": "pari",
                "raw": ["Paris"],
                "norm": ["pari"],
                "ctx_left": "",
                "ctx_right": "",
            },
            {
                "raw_text": "Today",
                "norm_text": "today",
                "raw": ["Today"],
                "norm": ["today"],
                "ctx_left": "",
                "ctx_right": "",
            },
        ]

        llm = DummyLLM('```json\n{"keep":[0]}\n```')
        kept = ex.llm_filter_candidates(candidates, llm, max_candidates=10)
        self.assertEqual([c["raw_text"] for c in kept], ["Paris"])


if __name__ == "__main__":
    unittest.main()
