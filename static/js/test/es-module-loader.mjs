import { readFile } from 'node:fs/promises';

const jsRoot = '/static/js/';

export async function load(url, context, defaultLoad) {
  if (
    url.endsWith('/topics-sunburst.js') ||
    url.endsWith('/topics-marimekko.js')
  ) {
    return {
      format: 'module',
      shortCircuit: true,
      source: `
        export default class TestChartStub {
          render() {}
        }
      `,
    };
  }

  if (url.startsWith('file:') && url.includes(jsRoot) && url.endsWith('.js')) {
    const source = await readFile(new URL(url), 'utf8');
    return {
      format: 'module',
      shortCircuit: true,
      source,
    };
  }

  return defaultLoad(url, context, defaultLoad);
}
