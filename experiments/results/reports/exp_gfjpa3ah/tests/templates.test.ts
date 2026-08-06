import { describe, it, expect, beforeAll } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import Handlebars from 'handlebars';
import { createTemplateEngine, registerHelpers } from '../src/templates.js';

async function makeTemplates(files: Record<string, string>): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'sitegen-tpl-'));
  for (const [rel, content] of Object.entries(files)) {
    const abs = path.join(dir, rel);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, content);
  }
  return dir;
}

describe('createTemplateEngine', () => {
  it('renders a layout with context', async () => {
    const dir = await makeTemplates({
      'layouts/default.hbs': '<h1>{{title}}</h1>{{{content}}}',
    });
    const engine = await createTemplateEngine(dir);
    expect(engine.render('default', { title: 'Hi', content: '<p>x</p>' })).toBe(
      '<h1>Hi</h1><p>x</p>',
    );
  });

  it('registers and renders partials', async () => {
    const dir = await makeTemplates({
      'layouts/default.hbs': '{{> nav}}<main>{{{content}}}</main>',
      'partials/nav.hbs': '<nav>{{site.title}}</nav>',
    });
    const engine = await createTemplateEngine(dir);
    expect(engine.render('default', { site: { title: 'S' }, content: 'c' })).toBe(
      '<nav>S</nav><main>c</main>',
    );
  });

  it('supports layout inheritance via {{!< parent}}', async () => {
    const dir = await makeTemplates({
      'layouts/default.hbs': '<html>{{{body}}}</html>',
      'layouts/post.hbs': '{{!< default}}\n<article>{{{content}}}</article>',
    });
    const engine = await createTemplateEngine(dir);
    expect(engine.render('post', { content: '<p>x</p>' })).toBe(
      '<html><article><p>x</p></article></html>',
    );
  });

  it('falls back to default for unknown layouts', async () => {
    const dir = await makeTemplates({ 'layouts/default.hbs': 'D:{{title}}' });
    const engine = await createTemplateEngine(dir);
    expect(engine.render('nope', { title: 't' })).toBe('D:t');
    expect(engine.hasLayout('nope')).toBe(false);
    expect(engine.hasLayout('default')).toBe(true);
  });

  it('throws when default layout is missing', async () => {
    const dir = await makeTemplates({ 'layouts/other.hbs': 'x' });
    await expect(createTemplateEngine(dir)).rejects.toThrow(/default\.hbs/);
  });

  it('detects circular layout inheritance', async () => {
    const dir = await makeTemplates({
      'layouts/default.hbs': '{{!< a}}\nD',
      'layouts/a.hbs': '{{!< default}}\nA{{{body}}}',
    });
    const engine = await createTemplateEngine(dir);
    expect(() => engine.render('a', {})).toThrow(/[Cc]ircular/);
  });
});

describe('helpers', () => {
  const hb = Handlebars.create();
  beforeAll(() => registerHelpers(hb as unknown as typeof Handlebars));

  it('formatDate formats with a pattern', () => {
    const t = hb.compile('{{formatDate d "MMMM DD, YYYY"}}');
    expect(t({ d: new Date('2026-01-15T00:00:00Z') })).toBe('January 15, 2026');
  });
  it('formatDate defaults to ISO date and tolerates junk', () => {
    const t = hb.compile('{{formatDate d}}');
    expect(t({ d: new Date('2026-01-15T00:00:00Z') })).toBe('2026-01-15');
    expect(t({ d: 'junk' })).toBe('');
  });
  it('limit slices arrays', () => {
    const t = hb.compile('{{#each (limit xs 2)}}{{this}}{{/each}}');
    expect(t({ xs: [1, 2, 3] })).toBe('12');
  });
  it('eq and join work', () => {
    expect(hb.compile('{{#if (eq a "x")}}Y{{/if}}')({ a: 'x' })).toBe('Y');
    expect(hb.compile('{{join xs "|"}}')({ xs: ['a', 'b'] })).toBe('a|b');
  });
});
