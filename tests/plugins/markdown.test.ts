import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { MarkdownPlugin } from '../../plugins/markdown';
import type { PluginContext } from '../../src/plugin';
import type { Page } from '../../src/types';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function skeleton(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'a',
    title: 'a',
    tags: [],
    html: '',
    sourcePath: 'a.md',
    outputFile: 'a.html',
    ...overrides,
  };
}

describe('MarkdownPlugin', () => {
  let contentDir: string;
  let ctx: PluginContext;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-md-plugin-');
    ctx = { contentDir, outputDir: '/unused', templatesDir: '/unused', config: {} };
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  it('parses frontmatter and renders Markdown into the page', () => {
    fs.writeFileSync(
      path.join(contentDir, 'a.md'),
      `---
title: My Post
date: 2024-01-01
tags: [x, y]
---
# Hello

Body **text**.
`
    );

    const plugin = new MarkdownPlugin();
    const page = plugin.onFile(skeleton(), ctx);

    expect(page.title).toBe('My Post');
    expect(page.date).toBe('2024-01-01');
    expect(page.tags).toEqual(['x', 'y']);
    expect(page.html).toContain('<h1>Hello</h1>');
    expect(page.html).toContain('<strong>text</strong>');
  });

  it('falls back to the skeleton slug as the title when frontmatter omits one', () => {
    fs.writeFileSync(path.join(contentDir, 'a.md'), 'No frontmatter here.');

    const plugin = new MarkdownPlugin();
    const page = plugin.onFile(skeleton({ slug: 'fallback-slug' }), ctx);

    expect(page.title).toBe('fallback-slug');
    expect(page.tags).toEqual([]);
    expect(page.date).toBeUndefined();
  });

  it('reads layout from frontmatter and trims it', () => {
    fs.writeFileSync(
      path.join(contentDir, 'a.md'),
      `---
title: Layout Test
layout: "  post  "
---
Body.
`
    );

    const plugin = new MarkdownPlugin();
    const page = plugin.onFile(skeleton(), ctx);
    expect(page.layout).toBe('post');
  });
});
