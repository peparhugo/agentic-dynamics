import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import os from 'node:os';
import path from 'node:path';
import fs from 'fs-extra';
import { buildSite } from '../src/generator.js';
import { startDevServer } from '../src/server.js';

function tmpDir(prefix: string) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `${prefix}-`));
  return dir;
}

async function writeFixture(root: string, files: Record<string, string>) {
  for (const [rel, content] of Object.entries(files)) {
    const abs = path.join(root, rel);
    await fs.ensureDir(path.dirname(abs));
    await fs.writeFile(abs, content, 'utf8');
  }
}

describe('Static Site Generator', () => {
  it('parses frontmatter and renders templates with layout', async () => {
    const src = tmpDir('src');
    const tpl = tmpDir('tpl');
    const out = tmpDir('out');

    await writeFixture(src, {
      'post.md': `---\ntitle: Hello\ndate: 2020-01-02\ntags: [a,b]\n---\n\n# Heading\n\n\n\n\ncode:\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n` + '```js\nconsole.log("x")\n```' + `\n`,
      'asset.txt': 'static',
    });
    await writeFixture(tpl, {
      'post.hbs': `<article><h1>{{title}}</h1><div class="content">{{{content}}}</div>{{> footer }}</article>`,
      'index.hbs': `<ul>{{#each pages}}<li><a href="{{this.url}}">{{this.data.title}}</a></li>{{/each}}</ul>`,
      'tag.hbs': `<h1>Tag: {{tag}}</h1><ul>{{#each pages}}<li>{{this.data.title}}</li>{{/each}}</ul>`,
      'partials/footer.hbs': `<footer>Footer</footer>`,
      'layouts/layout.hbs': `<!doctype html><html><body>{{{body}}}</body></html>`,
    });

    await buildSite({ sourceDir: src, templatesDir: tpl, outDir: out, baseUrl: 'http://example.com', siteTitle: 'Test Site', clean: true });

    const postHtml = await fs.readFile(path.join(out, 'post', 'index.html'), 'utf8');
    expect(postHtml).toContain('<h1>Hello</h1>');
    expect(postHtml).toContain('<footer>Footer</footer>');
    expect(postHtml).toMatch(/<pre><code class=\"hljs language-js\">/);

    const indexHtml = await fs.readFile(path.join(out, 'index.html'), 'utf8');
    expect(indexHtml).toContain('<ul>');
    expect(indexHtml).toContain('Hello');

    const tagHtml = await fs.readFile(path.join(out, 'tags', 'a', 'index.html'), 'utf8');
    expect(tagHtml).toContain('Tag: a');

    const rss = await fs.readFile(path.join(out, 'feed.xml'), 'utf8');
    expect(rss).toContain('<rss');
    expect(rss).toContain('<title>Test Site</title>');

    // asset copied
    const asset = await fs.readFile(path.join(out, 'asset.txt'), 'utf8');
    expect(asset).toBe('static');
  });

  it('respects draft flag unless includeDrafts', async () => {
    const src = tmpDir('src');
    const tpl = tmpDir('tpl');
    const out = tmpDir('out');
    await writeFixture(src, {
      'a.md': `---\ntitle: A\n---\nA`,
      'b.md': `---\ntitle: B\ndraft: true\n---\nB`,
    });
    await writeFixture(tpl, {
      'post.hbs': `{{{content}}}`,
      'layouts/layout.hbs': `{{{body}}}`,
    });

    await buildSite({ sourceDir: src, templatesDir: tpl, outDir: out, clean: true });
    expect(await fs.pathExists(path.join(out, 'a', 'index.html'))).toBe(true);
    expect(await fs.pathExists(path.join(out, 'b', 'index.html'))).toBe(false);

    await buildSite({ sourceDir: src, templatesDir: tpl, outDir: out, clean: true, includeDrafts: true });
    expect(await fs.pathExists(path.join(out, 'b', 'index.html'))).toBe(true);
  });

  it('injects live reload script during dev server builds', async () => {
    const src = tmpDir('src');
    const tpl = tmpDir('tpl');
    const out = tmpDir('out');
    await writeFixture(src, { 'index.md': '---\ntitle: Home\n---\nHello' });
    await writeFixture(tpl, {
      'post.hbs': `{{{content}}}`,
      'index.hbs': `index`,
      'layouts/layout.hbs': `<!doctype html><body>{{{body}}}</body>`,
    });

    const server = await startDevServer({ sourceDir: src, templatesDir: tpl, outDir: out, port: 5999 });
    const html = await fs.readFile(path.join(out, 'index.html'), 'utf8');
    expect(html).toContain('new WebSocket');
    await server.close();
  });
});
