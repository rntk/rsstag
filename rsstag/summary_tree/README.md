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
out-of-range references are rejected, valid entries in a batch are kept, and failed
batches are split and retried. Retries resume through the per-prompt answer cache:
identical evidence produces identical prompts, so completed work is replayed and
revalidated without new model calls.

`schema_version: 3` stores the node hierarchy (`kind`: root, topic, post, chunk) with
`path`, ordered `segments` and derived `statements`. The view walks that hierarchy;
selecting a post highlights its cited passages and, along the route, the parent
segments that cite each step. Schema 1 and 2 trees keep their previous display.
