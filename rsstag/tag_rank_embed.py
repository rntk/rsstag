"""TASK_TAGS_EMBED_RANK handler: writes rank.emb_norm for every tag of a user.

* ``rank.emb_norm``: L2 norm of the tag's Word2Vec vector, z-scored inside a bin
  of tags with similar log-frequency (raw norms correlate with frequency; within
  a bin a higher norm means a more informative word, Schakel & Wilson 2015).
  The user's model is trained on stemmed lemmas (``PostLemmaSentence``), so the
  vocabulary keys are exactly the tag names.

Contract: ``db.tags.bulk_write([UpdateOne(..., {"$set": {"rank.<key>": ...}})])``
for this task's own keys only, then ``tag_rank.recompute_derived(db, owner)``.
"""

import logging
import math
import os
import time
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
from pymongo import UpdateOne
from pymongo.database import Database

from rsstag.tag_rank import recompute_derived

log: logging.Logger = logging.getLogger("tag_rank_embed")

EMB_FREQ_BINS: int = 10
WRITE_BATCH_SIZE: int = 1000


@dataclass
class TagInfo:
    """Per-tag working state while computing this task's keys."""

    doc_id: Any
    tag: str
    freq: int
    norm: Optional[float] = None


# --- embedding norm ------------------------------------------------------


def _log_freq(freq: int) -> float:
    return math.log(max(int(freq), 1))


def _bin_edges(log_freqs: Sequence[float], bins: int) -> List[float]:
    """Quantile edges over sorted log-frequencies; duplicates collapse."""
    ordered: List[float] = sorted(log_freqs)
    count: int = len(ordered)
    edges: List[float] = [ordered[count * i // bins] for i in range(1, bins)]
    return sorted(set(edges))


def _z_scores(values: Sequence[float]) -> List[float]:
    """Population z-scores; a constant or single-item group scores 0."""
    count: int = len(values)
    mean: float = sum(values) / count
    std: float = math.sqrt(sum((v - mean) ** 2 for v in values) / count)
    if std <= 0.0:
        return [0.0] * count
    return [(v - mean) / std for v in values]


def emb_norm_zscores(
    entries: Sequence[Tuple[str, int, float]], bins: int = EMB_FREQ_BINS
) -> Dict[str, float]:
    """Z-score each ``(tag, freq, norm)`` norm within its log-frequency quantile bin."""
    if not entries:
        return {}
    edges: List[float] = _bin_edges([_log_freq(freq) for _, freq, _ in entries], bins)
    members: Dict[int, List[Tuple[str, float]]] = {}
    for tag, freq, norm in entries:
        bin_index: int = bisect_right(edges, _log_freq(freq))
        members.setdefault(bin_index, []).append((tag, norm))
    result: Dict[str, float] = {}
    for group in members.values():
        scores: List[float] = _z_scores([norm for _, norm in group])
        result.update((tag, score) for (tag, _), score in zip(group, scores))
    return result


def load_norms(path: str) -> Optional[Dict[str, float]]:
    """Map vocabulary key -> L2 norm of its vector; None when there is no model file."""
    if not os.path.isfile(path):
        return None
    from gensim.models.word2vec import Word2Vec

    wv: Any = Word2Vec.load(path).wv
    norms: Any = np.linalg.norm(wv.vectors, axis=1)
    return {key: float(norms[index]) for key, index in wv.key_to_index.items()}


def _model_path(db: Database, config: Dict[str, Any], owner: str) -> Optional[str]:
    user: Optional[Dict[str, Any]] = db.users.find_one({"sid": owner})
    name: Any = (user or {}).get("w2v")
    if not name:
        return None
    return os.path.join(config["settings"]["w2v_dir"], str(name))


def _find_norms(db: Database, config: Dict[str, Any], owner: str) -> Tuple[Optional[Dict[str, float]], bool]:
    """Return ``(norms, ok)``; ``ok`` is False only when a model exists but failed to load."""
    try:
        path: Optional[str] = _model_path(db, config, owner)
        norms: Optional[Dict[str, float]] = load_norms(path) if path else None
    except Exception as exc:
        log.error("Can`t load w2v model for owner %s. Info: %s", owner, exc)
        return None, False
    if norms is None:
        log.info("No w2v model for owner %s, emb_norm is skipped", owner)
    return norms, True


# --- run -----------------------------------------------------------------


def _scan_tags(
    db: Database,
    owner: str,
    norms: Optional[Dict[str, float]],
) -> Iterator[TagInfo]:
    cursor = db.tags.find({"owner": owner}, projection={"tag": True, "freq": True})
    for doc in cursor:
        tag: str = str(doc.get("tag") or "")
        if not tag:
            continue
        yield TagInfo(
            doc_id=doc["_id"],
            tag=tag,
            freq=int(doc.get("freq") or 0),
            norm=norms.get(tag) if norms is not None else None,
        )


def _apply_zscores(infos: List[TagInfo]) -> Dict[str, float]:
    entries: List[Tuple[str, int, float]] = [
        (info.tag, info.freq, info.norm) for info in infos if info.norm is not None
    ]
    return emb_norm_zscores(entries)


def _build_update(info: TagInfo, zscores: Dict[str, float]) -> Optional[UpdateOne]:
    if info.tag not in zscores:
        return None
    return UpdateOne(
        {"_id": info.doc_id},
        {"$set": {"rank.emb_norm": zscores[info.tag], "rank_pending": True}},
    )


def _write_updates(db: Database, updates: List[UpdateOne]) -> int:
    for start in range(0, len(updates), WRITE_BATCH_SIZE):
        db.tags.bulk_write(updates[start : start + WRITE_BATCH_SIZE], ordered=False)
    return len(updates)


def _compute_and_write(
    db: Database,
    owner: str,
    norms: Optional[Dict[str, float]],
) -> int:
    infos: List[TagInfo] = list(_scan_tags(db, owner, norms))
    zscores: Dict[str, float] = _apply_zscores(infos)
    updates: List[UpdateOne] = [
        update for update in (_build_update(i, zscores) for i in infos) if update
    ]
    return _write_updates(db, updates)


def run(db: Database, config: Dict[str, Any], owner: str) -> bool:
    """Compute this task's rank keys for ``owner``; True when the task is done."""
    started: float = time.monotonic()
    norms, model_ok = _find_norms(db, config, owner)
    try:
        written: int = _compute_and_write(db, owner, norms)
        recompute_derived(db, owner)
    except Exception as exc:
        log.error("Can`t write embed rank for owner %s. Info: %s", owner, exc)
        return False
    log.info(
        "Embed rank for owner %s: tags=%s vocab=%s model_ok=%s in %.2fs",
        owner,
        written,
        len(norms) if norms is not None else 0,
        model_ok,
        time.monotonic() - started,
    )
    return model_ok
