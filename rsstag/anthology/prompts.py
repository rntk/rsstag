"""Judge prompt builders. Static instructions first, variable data last."""

from typing import List, Sequence, Tuple

KINDS: Tuple[str, ...] = ("event", "debate", "howto", "release", "opinion", "analysis", "other")
SAMPLE_CHARS: int = 200

MERGE_INSTRUCTIONS: str = (
    "TASK: MERGE\n"
    "You compare pairs of snippet clusters taken from news and blog posts. "
    "For every pair decide whether both sides are about the same specific subject "
    "(same story, discussion, product or problem) and should be merged.\n"
    'Answer with exactly one line per pair: "<pair number>: same" or "<pair number>: different".\n'
    "No explanations, no other text.\n"
)

LABEL_INSTRUCTIONS: str = (
    "TASK: LABEL\n"
    "You judge clusters of text snippets taken from news and blog posts. For every cluster "
    "output one JSON object per line, nothing else:\n"
    '{"id": <cluster number>, "score": <1-5>, "label": "<at most 5 words>", "kind": "<kind>"}\n'
    "score: 5 = all snippets clearly share one specific subject, 3 = loosely related, "
    "1 = unrelated mix.\n"
    "label: a concrete name of the shared subject, at most 5 words, no quotes inside.\n"
    f"kind: one of {', '.join(KINDS)}.\n"
)

INTRUDER_INSTRUCTIONS: str = (
    "TASK: INTRUDER\n"
    "Every set below lists 5 numbered snippets. Four of them share a subject, one does not. "
    'For every set answer with exactly one line: "<set number>: <intruder snippet number>".\n'
    "No explanations, no other text.\n"
)

THEME_INSTRUCTIONS: str = (
    "TASK: THEMES\n"
    "Every group below joins several related subtopics. For every group output one JSON "
    "object per line, nothing else:\n"
    '{"id": <group number>, "label": "<at most 4 words>"}\n'
    "label: a short theme name covering all subtopics of the group.\n"
)


def clip_text(text: str, limit: int = SAMPLE_CHARS) -> str:
    flat: str = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _seed_line(seed: str) -> str:
    return f'Anthology subject: "{clip_text(seed, 80)}"\n\n' if seed else "\n"


def _bullets(samples: Sequence[str]) -> List[str]:
    return [f"- {clip_text(sample)}" for sample in samples]


def merge_prompt(pairs: Sequence[Tuple[List[str], List[str], List[str], List[str]]]) -> str:
    """pairs: (keywords A, samples A, keywords B, samples B)."""
    blocks: List[str] = []
    for number, (kw_a, sm_a, kw_b, sm_b) in enumerate(pairs, start=1):
        lines: List[str] = [f"Pair {number}", f"A keywords: {', '.join(kw_a)}", "A samples:"]
        lines += _bullets(sm_a)
        lines += [f"B keywords: {', '.join(kw_b)}", "B samples:"]
        lines += _bullets(sm_b)
        blocks.append("\n".join(lines))
    return MERGE_INSTRUCTIONS + "\n" + "\n\n".join(blocks)


def label_prompt(seed: str, clusters: Sequence[Tuple[List[str], List[str]]]) -> str:
    """clusters: (keywords, sample previews)."""
    blocks: List[str] = []
    for number, (keywords, samples) in enumerate(clusters, start=1):
        lines: List[str] = [f"Cluster {number}", f"keywords: {', '.join(keywords)}", "snippets:"]
        lines += _bullets(samples)
        blocks.append("\n".join(lines))
    return LABEL_INSTRUCTIONS + _seed_line(seed) + "\n\n".join(blocks)


def intruder_prompt(sets: Sequence[Sequence[str]]) -> str:
    """sets: five snippet previews each (already shuffled)."""
    blocks: List[str] = []
    for number, items in enumerate(sets, start=1):
        lines: List[str] = [f"Set {number}"]
        lines += [f"{pos}. {clip_text(text)}" for pos, text in enumerate(items, start=1)]
        blocks.append("\n".join(lines))
    return INTRUDER_INSTRUCTIONS + "\n" + "\n\n".join(blocks)


def theme_prompt(seed: str, groups: Sequence[Tuple[List[str], List[str]]]) -> str:
    """groups: (child labels, keywords)."""
    blocks: List[str] = []
    for number, (labels, keywords) in enumerate(groups, start=1):
        blocks.append(
            f"Group {number}\nsubtopics: {'; '.join(labels)}\nkeywords: {', '.join(keywords)}"
        )
    return THEME_INSTRUCTIONS + _seed_line(seed) + "\n\n".join(blocks)
