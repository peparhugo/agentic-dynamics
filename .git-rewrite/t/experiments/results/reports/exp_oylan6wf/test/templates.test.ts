import { describe, expect, it, beforeEach } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { TemplateEngine } from '../src/templates.js';

describe('TemplateEngine', () => {
  let engine: TemplateEngine;
  beforeEach(() => {
    engine = new TemplateEngine();
  });

  it('renders a named template with context', () => {
    engine.addTemplate('greet', 'Hello, {{name}}!');
    expect(engine.renderTemplate('greet', { name: 'World' })).toBe('Hello, World!');
  });

  it('throws for unknown templates and layouts', () => {
    expect(() => engine.renderTemplate('nope', {})).toThrow(/Template not found/);
    expect(() =>
      engine.renderPage({ layout: 'missing', content: 'x', context: {} }),
    ).toThrow(/Layout not found/);
  });

  it('renders partials', () => {
    engine.addPartial('header', '<h1>{{title}}</h1>');
    engine.addTemplate('page', '{{> header}}<p>{{body}}</p>');
    expect(engine.renderTemplate('page', { title: 'T', body: 'B' })).toBe(
      '<h1>T</h1><p>B</p>',
    );
  });

  it('wraps content in a layout via {{{content}}}', () => {
    engine.addLayout('default', '<html><body>{{{content}}}</body></html>');
    const html = engine.renderPage({
      content: '<p>inner</p>',
      context: { title: 'x' },
    });
    expect(html).toBe('<html><body><p>inner</p></body></html>');
  });

  it('layout receives page context too', () => {
    engine.addLayout('default', '<title>{{title}}</title>{{{content}}}');
    const html = engine.renderPage({ content: 'B', context: { title: 'My Page' } });
    expect(html).toBe('<title>My Page</title>B');
  });

  it('passes content through when no default layout exists', () => {
    expect(engine.renderPage({ content: '<p>raw</p>', context: {} })).toBe('<p>raw</p>');
  });

  it('does not escape HTML content in layouts but escapes {{vars}}', () => {
    engine.addLayout('default', '{{unsafe}}|{{{content}}}');
    const html = engine.renderPage({
      content: '<em>ok</em>',
      context: { unsafe: '<script>' },
    });
    expect(html).toBe('&lt;script&gt;|<em>ok</em>');
  });

  it('supports built-in helpers: formatDate, eq, join', () => {
    engine.addTemplate(
      't',
      '{{formatDate d}}|{{formatDate d "iso"}}|{{#if (eq a b)}}same{{/if}}|{{join tags "/"}}',
    );
    const out = engine.renderTemplate('t', {
      d: new Date('2024-01-02T03:04:05Z'),
      a: 1,
      b: 1,
      tags: ['x', 'y'],
    });
    expect(out).toBe('2024-01-02|2024-01-02T03:04:05.000Z|same|x/y');
  });

  it('loads templates, layouts, and partials from a directory', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'sprout-tpl-'));
    await fs.mkdir(path.join(dir, 'layouts'));
    await fs.mkdir(path.join(dir, 'partials'));
    await fs.writeFile(path.join(dir, 'layouts', 'default.hbs'), '<L>{{{content}}}</L>');
    await fs.writeFile(path.join(dir, 'partials', 'nav.hbs'), '<nav/>');
    await fs.writeFile(path.join(dir, 'page.hbs'), '{{> nav}}{{title}}');

    await engine.loadDirectory(dir);
    const html = engine.renderPage({ template: 'page', context: { title: 'Hi' } });
    expect(html).toBe('<L><nav/>Hi</L>');
    await fs.rm(dir, { recursive: true, force: true });
  });
});
