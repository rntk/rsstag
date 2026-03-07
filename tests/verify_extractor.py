import sys
import os
import json
import unittest
from typing import List

# Setup path to import rsstag
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rsstag.entity_extractor import RssTagEntityExtractor, LLMClient


class MockLLM(LLMClient):
    def __init__(self, response: str):
        self.response = response
        self.last_prompt = None

    def call(self, user_msgs: List[str], temperature: float = 0.0) -> str:
        self.last_prompt = user_msgs[0]
        return self.response


class TestRssTagEntityExtractorImproved(unittest.TestCase):
    def setUp(self):
        self.extractor = RssTagEntityExtractor()

    def test_verify_entity_in_text(self):
        text = (
            "Apple released the new iPhone 15 in Cupertino today. Tim Cook was present."
        )

        # Exact match
        self.assertTrue(self.extractor._verify_entity_in_text("Apple", text))
        self.assertTrue(self.extractor._verify_entity_in_text("iPhone 15", text))

        # Case insensitive
        self.assertTrue(self.extractor._verify_entity_in_text("apple", text))
        self.assertTrue(self.extractor._verify_entity_in_text("iphone 15", text))

        # Whitespace handling
        self.assertTrue(self.extractor._verify_entity_in_text("iPhone  15", text))

        # Hallucination (doesn't exist)
        self.assertFalse(self.extractor._verify_entity_in_text("Google", text))
        self.assertFalse(self.extractor._verify_entity_in_text("iPhone 16", text))

    def test_discovery_mode_success(self):
        text = "Mark Zuckerberg visited Paris last week."
        llm_response = json.dumps(
            [
                {"entity": "Mark Zuckerberg", "type": "PERSON"},
                {"entity": "Paris", "type": "LOC"},
            ]
        )
        mock_llm = MockLLM(llm_response)

        results = self.extractor.extract_entities_discovery(text, mock_llm)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["entity_str"], "Mark Zuckerberg")
        self.assertEqual(results[0]["type"], "PERSON")
        self.assertEqual(results[1]["entity_str"], "Paris")
        self.assertEqual(results[1]["type"], "LOC")

    def test_discovery_mode_hallucination_prevention(self):
        text = "Elon Musk is the CEO of Tesla."
        # LLM hallucinating Jeff Bezos
        llm_response = json.dumps(
            [
                {"entity": "Elon Musk", "type": "PERSON"},
                {"entity": "Jeff Bezos", "type": "PERSON"},
                {"entity": "Tesla", "type": "ORG"},
            ]
        )
        mock_llm = MockLLM(llm_response)

        results = self.extractor.extract_entities_discovery(text, mock_llm)

        # Jeff Bezos should be discarded
        self.assertEqual(len(results), 2)
        entities = [r["entity_str"] for r in results]
        self.assertIn("Elon Musk", entities)
        self.assertIn("Tesla", entities)
        self.assertNotIn("Jeff Bezos", entities)

    def test_sentence_starters_filtering(self):
        # "В" is a common Russian sentence starter (preposition)
        text = "В Москве прошел дождь. Сегодня хорошая погода."
        candidates = self.extractor.extract_entity_candidates(text)

        # "В" and "Сегодня" should NOT be candidates
        candidate_strs = [c["entity_str"].lower() for c in candidates]
        self.assertNotIn("в", candidate_strs)
        self.assertNotIn("сегодня", candidate_strs)
        self.assertIn("москве", candidate_strs)

    def test_extract_entities_with_llm_discovery(self):
        text = "Alphabet Inc. is based in Mountain View."
        llm_response = json.dumps(
            [
                {"entity": "Alphabet Inc.", "type": "ORG"},
                {"entity": "Mountain View", "type": "LOC"},
            ]
        )
        mock_llm = MockLLM(llm_response)

        # Test normalized extraction using discovery
        entities = self.extractor.extract_entities_with_llm(
            text, mock_llm, use_discovery=True
        )

        # Alphabet Inc -> alphabet inc (after treat_entities it depends on stemmer)
        # But we expect the LIST of words
        self.assertTrue(len(entities) >= 1)
        # Check Alphabet
        self.assertIn("alphabet", [w for ent in entities for w in ent])


if __name__ == "__main__":
    unittest.main()
