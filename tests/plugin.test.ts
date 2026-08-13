import type { Page } from '../src/generator.js';
import { SsgEngine, type Plugin } from '../src/generator.js';

describe('SsgEngine', () => {
  it('runs every lifecycle hook in plugin order', async () => {
    const events: string[] = [];
    const page: Page = { slug: 'page', title: 'Page', tags: [], html: '', data: {} };
    const plugin = (name: string): Plugin => ({
      onStart: () => { events.push(`${name}:start`); },
      beforeBuild: (context) => { events.push(`${name}:before`); if (name === 'first') context.pages.push(page); },
      onFile: (currentPage) => { events.push(`${name}:file:${currentPage.slug}`); },
      afterBuild: () => { events.push(`${name}:after`); },
      onEnd: () => { events.push(`${name}:end`); }
    });

    const pages = await new SsgEngine({}, [plugin('first'), plugin('second')]).build();

    expect(pages).toEqual([page]);
    expect(events).toEqual([
      'first:start', 'second:start', 'first:before', 'second:before',
      'first:file:page', 'second:file:page', 'first:after', 'second:after',
      'first:end', 'second:end'
    ]);
  });
});
