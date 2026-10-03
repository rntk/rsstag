import unittest

from rsstag.anthology import prompts
from rsstag.anthology.parsers import (
    clip_words,
    parse_intruders,
    parse_json_objects,
    parse_labels,
    parse_pair_answers,
    parse_theme_labels,
)


class TestAnthologyParsers(unittest.TestCase):
    def test_json_objects_from_fenced_lines_with_noise(self) -> None:
        raw = 'Sure! Here:\n```json\n{"id": 1, "x": 2}\n{"id": 2}\n```\nDone.'
        self.assertEqual(parse_json_objects(raw), [{"id": 1, "x": 2}, {"id": 2}])

    def test_json_objects_from_array_and_single_quotes(self) -> None:
        self.assertEqual(parse_json_objects('[{"id": 1}, 5]'), [{"id": 1}])
        self.assertEqual(parse_json_objects("{'id': 3}"), [{"id": 3}])
        self.assertEqual(parse_json_objects(""), [])
        self.assertEqual(parse_json_objects("no json here"), [])

    def test_parse_labels_defaults_and_clamping(self) -> None:
        raw = (
            '{"id": 1, "score": 9, "label": "A very long label with many words", "kind": "Event"}\n'
            '{"id": "2", "score": "x", "label": "Ok", "kind": "weird"}\n'
            '{"id": 7, "score": 4, "label": "out of range"}\n'
            '{"id": 1, "score": 1, "label": "duplicate"}'
        )
        result = parse_labels(raw, 3)
        self.assertEqual(set(result), {1, 2})
        self.assertEqual(result[1].score, 5)
        self.assertEqual(result[1].label, "A very long label with")
        self.assertEqual(result[1].kind, "event")
        self.assertEqual(result[2].score, 3)
        self.assertEqual(result[2].kind, "other")

    def test_parse_pair_answers(self) -> None:
        raw = "1: same\nPair 2 - different\n3. YES\n4: maybe\n9: same\n1: different"
        self.assertEqual(parse_pair_answers(raw, 4), {1: True, 2: False, 3: True})
        self.assertEqual(parse_pair_answers("", 3), {})

    def test_parse_intruders_lines_and_json(self) -> None:
        self.assertEqual(parse_intruders("1: 3\nSet 2: #5\n3: 9\n", 3), {1: 3, 2: 5})
        self.assertEqual(parse_intruders('[{"id": 1, "intruder": 2}]', 2), {1: 2})
        self.assertEqual(parse_intruders("garbage", 2), {})

    def test_parse_theme_labels(self) -> None:
        raw = '```\n{"id": 1, "label": "\\"Space race news today\\" extra"}\n{"id": 2, "label": ""}\n```'
        self.assertEqual(parse_theme_labels(raw, 2), {1: "Space race news today"})

    def test_clip_words(self) -> None:
        self.assertEqual(clip_words('  "Hello big world."  ', 5), "Hello big world")
        self.assertEqual(clip_words("a b c d e f", 4), "a b c d")

    def test_prompts_put_instructions_first(self) -> None:
        prompt = prompts.label_prompt("seed", [(["kw"], ["text one"])])
        self.assertTrue(prompt.startswith(prompts.LABEL_INSTRUCTIONS))
        self.assertTrue(prompt.rstrip().endswith("- text one"))
        merge = prompts.merge_prompt([(["a"], ["x"], ["b"], ["y"])])
        self.assertIn("Pair 1", merge)
        intruder = prompts.intruder_prompt([["1", "2", "3", "4", "5"]])
        self.assertIn("5. 5", intruder)
        self.assertLessEqual(len(prompts.clip_text("x" * 500)), prompts.SAMPLE_CHARS)


if __name__ == "__main__":
    unittest.main()
