/**
 * On-demand topic-run summaries for the post canvas. Requests go through the
 * existing `/openai/summary` endpoint, are cached per card key, and run with
 * bounded concurrency so summary mode does not flood the provider.
 */

const DEFAULT_CONCURRENCY = 2;

/**
 * @typedef {{status: 'idle'|'queued'|'loading'|'done'|'error', text?: string, error?: string}} SummaryEntry
 */

/**
 * @param {{topic: string, sentences: string[]}} body
 * @param {typeof fetch} fetchImpl
 * @returns {Promise<string>}
 */
export async function fetchTopicSummary(body, fetchImpl = fetch) {
  if (!body.sentences.length) throw new Error('This topic has no text to summarize.');
  const response = await fetchImpl('/openai/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let result = null;
  try {
    result = await response.json();
  } catch {
    result = null;
  }
  if (!response.ok || !result?.data) {
    throw new Error(result?.error || 'Unable to generate summary. Please try again.');
  }
  return result.data;
}

/**
 * @param {{
 *   buildRequest: function(object): {topic: string, sentences: string[]},
 *   onUpdate: function(string, SummaryEntry): void,
 *   fetchSummary?: function({topic: string, sentences: string[]}): Promise<string>,
 *   concurrency?: number,
 * }} options
 */
export function createSummaryStore({
  buildRequest,
  onUpdate,
  fetchSummary = (body) => fetchTopicSummary(body),
  concurrency = DEFAULT_CONCURRENCY,
}) {
  /** @type {Map<string, SummaryEntry>} */
  const entries = new Map();
  const queue = [];
  let running = 0;

  const set = (key, entry) => {
    entries.set(key, entry);
    onUpdate(key, entry);
  };

  const run = async (card) => {
    running += 1;
    set(card.key, { status: 'loading' });
    try {
      set(card.key, { status: 'done', text: await fetchSummary(buildRequest(card)) });
    } catch (error) {
      console.error('Topic summary request failed', error);
      set(card.key, { status: 'error', error: error.message || 'Unable to generate summary.' });
    } finally {
      running -= 1;
      pump();
    }
  };

  const pump = () => {
    while (running < concurrency && queue.length) run(queue.shift());
  };

  return {
    /** @param {string} key @returns {SummaryEntry} */
    get: (key) => entries.get(key) || { status: 'idle' },
    /** Queue a card unless it is already cached or pending. Errors are retried. */
    request(card) {
      const status = entries.get(card.key)?.status;
      if (status && status !== 'error') return;
      set(card.key, { status: 'queued' });
      queue.push(card);
      pump();
    },
  };
}
