# Post summary trees

This implementation adapts `example/`'s summary model to post text. The evidence
hierarchy and the reader's claim tree are separate structures.

* Each post supplies stable, numbered passages (including its title). Long posts
  are split into bounded chunks; the entire cleaned text is retained.
* Posts remain in the selected source order. Balanced groups bound each branch to
  eight children. These groups organize evidence; they do not classify posts as
  mutually exclusive topics. Topic paths in the view come from cited claims.
* Generation proceeds bottom-up, batching ready nodes within character and count
  limits. Leaves cite passage ranges. Parents cite exact child segment positions.
  Prompts preserve attribution, uncertainty and contradictory reporting.
* Every substantive segment requires valid local citations. Unknown ids, duplicate
  ids and out-of-range references are rejected. Valid entries are saved even when
  others in the batch fail. Requests retry and split unresolved batches. Identical
  child prose is relayed with explicit links, without a model call.
* Results are checkpointed under the active run id. Retries restore completed
  nodes only if evidence, hierarchy, focus and generation instructions match.
  Cached answers are revalidated. A failed request never silently makes a post
  irrelevant or attaches it to an arbitrary statement.
* The display follows claim citations as occurrences: the same post or claim may
  appear on multiple paths. Repeated single-child prose is merged for display;
  uncited children stay reachable. Selecting a source shows its cited passages;
  route summaries highlight the traversed segments.

`schema_version: 2` stores ordered `segments` with explicit `claim` or `rows`
sources. `statements` and their post ids are derived for source navigation, never
used to infer claim links. Older saved trees keep their previous display until
rebuilt. Existing model-answer caches remain isolated by changed prompt hashes.
