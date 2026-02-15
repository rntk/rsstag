import gzip
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Set
from urllib.parse import quote

from werkzeug.wrappers import Response

from rsstag.stopwords import stopwords

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


@dataclass(frozen=True)
class KeywordItem:
    phrase: str
    score: float
    frequency: int


def _load_lemmas_texts(app: "RSSTagApplication", user: dict) -> List[str]:
    only_unread: Optional[bool] = user["settings"]["only_unread"] or None
    posts: Iterable[dict] = app.posts.get_all(
        user["sid"], only_unread, projection={"lemmas": True}
    )
    texts: List[str] = []
    for post in posts:
        lemmas_data: Optional[bytes] = post.get("lemmas")
        if not isinstance(lemmas_data, (bytes, bytearray)):
            continue
        text: str = gzip.decompress(lemmas_data).decode("utf-8", "replace").strip()
        if text:
            texts.append(text)
    return texts


def _tokenize_lemmas_text(text: str) -> List[str]:
    tokens: List[str] = []
    raw_tokens: List[str] = text.split()
    for token in raw_tokens:
        normalized: str = token.strip().casefold()
        if not normalized or len(normalized) < 2 or normalized.isdigit():
            continue
        tokens.append(normalized)
    return tokens


def _get_stopwords() -> Set[str]:
    return set(stopwords.words("english") + stopwords.words("russian"))


def _extract_rake_keywords(
    texts: List[str], stop_words: Set[str], max_keywords: int
) -> List[KeywordItem]:
    phrase_freq: Counter[str] = Counter()
    word_freq: Counter[str] = Counter()
    word_degree: Counter[str] = Counter()

    for text in texts:
        tokens: List[str] = _tokenize_lemmas_text(text)
        current_phrase: List[str] = []
        for token in tokens:
            if token in stop_words:
                if current_phrase:
                    phrase: str = " ".join(current_phrase)
                    phrase_freq[phrase] += 1
                    phrase_len: int = len(current_phrase)
                    for phrase_word in current_phrase:
                        word_freq[phrase_word] += 1
                        word_degree[phrase_word] += max(0, phrase_len - 1)
                    current_phrase = []
                continue
            current_phrase.append(token)
        if current_phrase:
            phrase = " ".join(current_phrase)
            phrase_freq[phrase] += 1
            phrase_len = len(current_phrase)
            for phrase_word in current_phrase:
                word_freq[phrase_word] += 1
                word_degree[phrase_word] += max(0, phrase_len - 1)

    word_score: Dict[str, float] = {}
    for word, freq in word_freq.items():
        if freq <= 0:
            continue
        degree: int = word_degree[word] + freq
        word_score[word] = degree / float(freq)

    ranked: List[KeywordItem] = []
    for phrase, freq in phrase_freq.items():
        words: List[str] = phrase.split()
        score: float = 0.0
        for word in words:
            score += word_score.get(word, 0.0)
        if score <= 0.0:
            continue
        ranked.append(KeywordItem(phrase=phrase, score=score, frequency=freq))

    ranked.sort(key=lambda item: (item.score, item.frequency, item.phrase), reverse=True)
    return ranked[:max_keywords]


def _extract_yake_keywords(
    texts: List[str], stop_words: Set[str], max_keywords: int
) -> List[KeywordItem]:
    docs_tokens: List[List[str]] = [_tokenize_lemmas_text(text) for text in texts]
    docs_tokens = [tokens for tokens in docs_tokens if tokens]
    if not docs_tokens:
        return []

    total_docs: int = len(docs_tokens)
    total_tokens: int = sum(len(tokens) for tokens in docs_tokens)
    if total_tokens <= 0:
        return []

    word_tf: Counter[str] = Counter()
    word_df: Counter[str] = Counter()
    word_positions: defaultdict[str, List[float]] = defaultdict(list)
    for tokens in docs_tokens:
        seen_in_doc: Set[str] = set()
        doc_len: int = len(tokens)
        for idx, token in enumerate(tokens):
            if token in stop_words:
                continue
            word_tf[token] += 1
            if token not in seen_in_doc:
                seen_in_doc.add(token)
                word_df[token] += 1
                word_positions[token].append((idx + 1) / float(doc_len + 1))

    word_weight: Dict[str, float] = {}
    for token, tf in word_tf.items():
        df: int = word_df.get(token, 1)
        avg_pos: float = sum(word_positions[token]) / float(len(word_positions[token]))
        tf_norm: float = tf / float(total_tokens)
        idf: float = math.log((1.0 + total_docs) / (1.0 + df)) + 1.0
        position_boost: float = 1.0 / (0.3 + avg_pos)
        word_weight[token] = tf_norm * idf * position_boost

    candidate_freq: Counter[str] = Counter()
    candidate_df: Counter[str] = Counter()
    candidate_first_pos: defaultdict[str, List[float]] = defaultdict(list)

    for tokens in docs_tokens:
        doc_len = len(tokens)
        seen_candidates: Set[str] = set()
        for start_idx in range(doc_len):
            if tokens[start_idx] in stop_words:
                continue
            for n_size in (1, 2, 3):
                end_idx: int = start_idx + n_size
                if end_idx > doc_len:
                    break
                phrase_words: List[str] = tokens[start_idx:end_idx]
                if any(word in stop_words for word in phrase_words):
                    continue
                phrase: str = " ".join(phrase_words)
                candidate_freq[phrase] += 1
                if phrase not in seen_candidates:
                    seen_candidates.add(phrase)
                    candidate_df[phrase] += 1
                    candidate_first_pos[phrase].append((start_idx + 1) / float(doc_len + 1))

    ranked: List[KeywordItem] = []
    for phrase, freq in candidate_freq.items():
        phrase_words = phrase.split()
        if not phrase_words:
            continue
        word_scores_sum: float = sum(word_weight.get(word, 0.0) for word in phrase_words)
        avg_word_score: float = word_scores_sum / float(len(phrase_words))
        df_boost: float = 1.0 + (candidate_df.get(phrase, 1) / float(total_docs))
        first_pos_values: List[float] = candidate_first_pos.get(phrase, [1.0])
        avg_first_pos: float = sum(first_pos_values) / float(len(first_pos_values))
        early_boost: float = 1.0 / (0.5 + avg_first_pos)
        freq_boost: float = math.log1p(freq)
        score: float = avg_word_score * df_boost * early_boost * freq_boost
        if score <= 0.0:
            continue
        ranked.append(KeywordItem(phrase=phrase, score=score, frequency=freq))

    ranked.sort(key=lambda item: (item.score, item.frequency, item.phrase), reverse=True)
    return ranked[:max_keywords]


def _render_keywords_page(
    app: "RSSTagApplication",
    user: dict,
    page_number: int,
    endpoint: str,
    keywords: List[KeywordItem],
    title: str,
) -> Response:
    items_on_page: int = user["settings"]["tags_on_page"]
    page_count: int = app.get_page_count(len(keywords), items_on_page)
    if page_count <= 0:
        page_count = 1

    current_page: int = page_number
    if current_page <= 0:
        current_page = 1
    elif current_page > page_count:
        current_page = page_count

    pager_index: int = current_page - 1
    if pager_index < 0:
        pager_index = 1
    pages_map, start_range, end_range = app.calc_pager_data(
        pager_index, page_count, items_on_page, endpoint
    )

    page_keywords: List[KeywordItem] = keywords[start_range:end_range]
    sorted_tags: List[dict] = []
    for item in page_keywords:
        sorted_tags.append(
            {
                "tag": item.phrase,
                "url": app.routes.get_url_by_endpoint(
                    endpoint="on_entity_get", params={"quoted_tag": quote(item.phrase)}
                ),
                "words": [item.phrase],
                "count": round(item.score, 4),
                "sentiment": [],
            }
        )

    page = app.template_env.get_template("group-by-tag.html")
    return Response(
        page.render(
            tags=sorted_tags,
            sort_by_title=title,
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint=endpoint, params={"page_number": current_page}
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            tags_categories_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_categories_get", params={"page_number": 1}
            ),
            pages_map=pages_map,
            current_page=current_page,
            letters=[],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_group_by_rake_dyn_get(
    app: "RSSTagApplication", user: dict, page_number: int = 1
) -> Response:
    texts: List[str] = _load_lemmas_texts(app, user)
    stop_words: Set[str] = _get_stopwords()
    keywords: List[KeywordItem] = _extract_rake_keywords(
        texts=texts,
        stop_words=stop_words,
        max_keywords=max(50, user["settings"]["tags_on_page"] * 12),
    )
    return _render_keywords_page(
        app=app,
        user=user,
        page_number=page_number,
        endpoint="on_group_by_rake_dyn_get",
        keywords=keywords,
        title="RAKE dynamic",
    )


def on_group_by_yake_dyn_get(
    app: "RSSTagApplication", user: dict, page_number: int = 1
) -> Response:
    texts: List[str] = _load_lemmas_texts(app, user)
    stop_words: Set[str] = _get_stopwords()
    keywords: List[KeywordItem] = _extract_yake_keywords(
        texts=texts,
        stop_words=stop_words,
        max_keywords=max(50, user["settings"]["tags_on_page"] * 12),
    )
    return _render_keywords_page(
        app=app,
        user=user,
        page_number=page_number,
        endpoint="on_group_by_yake_dyn_get",
        keywords=keywords,
        title="YAKE dynamic",
    )
