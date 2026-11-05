# Post summary trees

A progressive-disclosure tree: each level down is more specific and more detailed,
ending at the cited passages of the source posts.

```
focus (apple)            one-line overview naming the categories
├─ iPhone                abstract overview of its sub-topics
│  ├─ Battery life       detailed summary: names, numbers, disagreements
│  │  ├─ post            brief focused summary → cited passages
│  │  └─ post
│  └─ Accessories
└─ macOS
```

Pipeline stages (`pipeline.py`):

1. **posts** — every post gets a brief, focus-specific summary citing its numbered
   passages (long posts are summarized per passage chunk first). Irrelevant posts
   return no segments and are skipped; a post that never gets a valid answer is
   reported as `summary failed` instead of aborting the run.
2. **topics** (`topics.py`) — only the short post digests are sent to the model,
   which splits them into 2–7 distinct, mutually exclusive sub-topics one level more
   specific than the current path; any topic with more than `LEAF_MAX_POSTS` posts is
   split again, up to `MAX_DEPTH` levels. Large sets are assigned in batches against
   the topics found so far. Invalid answers are rejected; unassigned posts go to
   "Other"; when no real split is found the posts stay directly under the topic.
3. **summaries** — bottom-up along that structure, each level with its own intent
   (`generation.LEVEL_INTENTS`): `detail` just above posts, `overview` for topics of
   topics, `root` for the focus. Every segment cites child claims (`C1.S2`), so any
   statement resolves down to post passages.

Every substantive segment requires valid local citations; unknown, duplicate and
out-of-range references are rejected. Invalid items are retried independently. Retries resume through the per-prompt answer cache:
identical evidence produces identical prompts, so completed work is replayed and
revalidated without new model calls.

`schema_version: 3` stores the node hierarchy (`kind`: root, topic, post, chunk) with
`path`, ordered `segments` and derived `statements`. The view walks that hierarchy;
selecting a post highlights its cited passages and, along the route, the parent
segments that cite each step. Schema 1 and 2 trees keep their previous display.

Execution is dependency-driven: independent nodes run concurrently and a parent
becomes eligible as soon as its children finish. Workers return validated segments;
only the coordinator changes the tree or publishes snapshots. Topic proposals and
assignments for independent branches also run concurrently, with deterministic
assembly afterwards. The schema-v3 API and citation paths are unchanged.

Each generation request contains one node under the stable local id `item`.
Successful results are cached independently of tree-local ids and article order;
cache keys include the resolved provider handler and model. A failed node has at
most three attempts (with the default retry policy), with no recursive batch
splitting or regeneration of successful siblings. Cached answers still pass local
citation validation and the configured claim verifier. A detailed-topic answer
whose every claim is rejected is regenerated within that same retry budget; it
is no longer retained as unsupported prose.

`[settings] summary_tree_workers` controls generation concurrency (1–32); a user
setting with the same name overrides the server default. Hosted providers default
to four slots and llama.cpp to one. Decisions retain their separate
`[decisions] summary_tree_workers` limit, enforced across all concurrent callers
(including nested topic-assignment batches). Existing request timeout settings still
apply. Generation and topic planning heartbeat every ten seconds while awaiting
results; partial snapshots publish at most once per second, and throttled changes
are flushed at every stage change and before a run is marked failed.

The run aborts after `MAX_OUTAGE_ASKS` consecutive outages (asks that got no answer
at all). Concurrent asks that overlap an outage already counted count once, so a
single blip does not abort a run just because several workers were in flight.
When the coordinator fails or is superseded, queued work is cancelled and running
workers stop before their next LLM attempt instead of being joined.

Metrics now include `llm_attempts` (actual provider attempts),
`llm_invalid_answers`, `llm_request_seconds` (sum of request durations, which can
exceed elapsed time under concurrency), and `stage_seconds`. `llm_calls` retains
its original meaning of logical requests. Compare cold and warm runs on the same
corpus before increasing concurrency; rate limits and local server capacity can
limit the benefit.
