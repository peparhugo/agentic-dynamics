import { createPipeline } from '../src/plugin';
import type { Plugin, PluginContext } from '../src/plugin';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/template';
import type { Page } from '../src/types';

function makeContext(): PluginContext {
  return {
    contentDir: '.',
    outputDir: '.',
    templatesDir: '.',
    pages: [],
    config: {},
  };
}

describe('createPipeline', () => {
  it('runs each lifecycle hook across all plugins in order', async () => {
    const order: string[] = [];
    const first: Plugin = {
      name: 'first',
      onStart: () => {
        order.push('first:start');
      },
      onEnd: () => {
        order.push('first:end');
      },
    };
    const second: Plugin = {
      name: 'second',
      onStart: () => {
        order.push('second:start');
      },
      onEnd: () => {
        order.push('second:end');
      },
    };

    const pipeline = createPipeline([first, second], makeContext());
    await pipeline.onStart();
    await pipeline.onEnd();

    expect(order).toEqual(['first:start', 'second:start', 'first:end', 'second:end']);
  });

  it('passes the page to onFile hooks in order', async () => {
    const seen: string[] = [];
    const page: Page = { slug: 'x', title: 'X', tags: [], html: '' };
    const plugins: Plugin[] = [
      { name: 'a', onFile: (p) => void seen.push(`a:${p.slug}`) },
      { name: 'b', onFile: (p) => void seen.push(`b:${p.slug}`) },
    ];

    await createPipeline(plugins, makeContext()).onFile(page);

    expect(seen).toEqual(['a:x', 'b:x']);
  });
});

describe('MarkdownPlugin', () => {
  it('renders raw markdown into page.html', async () => {
    const page = { slug: 'x', title: 'X', tags: [], html: '', markdown: '# Hi' };
    await new MarkdownPlugin().onFile(page);
    expect(page.html).toContain('<h1>Hi</h1>');
  });

  it('leaves pages without markdown untouched', async () => {
    const page: Page = { slug: 'x', title: 'X', tags: [], html: '<p>kept</p>' };
    await new MarkdownPlugin().onFile(page);
    expect(page.html).toBe('<p>kept</p>');
  });
});

describe('TemplatePlugin', () => {
  it('renders pages after beforeBuild has run', async () => {
    const plugin = new TemplatePlugin();
    await plugin.beforeBuild?.({
      contentDir: '.',
      outputDir: '.',
      templatesDir: '.',
      pages: [],
      config: {},
    });

    const html = plugin.renderPage({ slug: 'x', title: 'Hello', tags: [], html: '<p>body</p>' });
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>body</p>');
  });
});
