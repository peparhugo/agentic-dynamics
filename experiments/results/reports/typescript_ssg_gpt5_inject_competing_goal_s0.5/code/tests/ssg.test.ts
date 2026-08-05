import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import path from 'node:path';
import fs from 'node:fs/promises';
import { buildSite } from '../src/build';
import { startDevServer } from '../src/server';

const tmpOut = path.join(process.cwd(), 'tmp_out');
const fixtures = path.join(process.cwd(), 'tests/fixtures');

describe('frontmatter parsing and build', () => {
  it('builds pages, excludes drafts by default, generates tags and rss', async () => {
    await fs.rm(tmpOut, { recursive: true, force: true });
    const { pages, tags } = await buildSite({
      srcDir: path.join(fixtures, 'src'),
      templatesDir: path.join(fixtures, 'templates'),
      outDir: tmpOut,
      baseUrl: 'http://example.com',
      includeDrafts: false,
      clean: true
    });
    expect(pages.length).toBe(1);
    const html = await fs.readFile(path.join(tmpOut, 'post1.html'), 'utf8');
    expect(html).toContain('<h1>My Site</h1>');
    expect(html).toContain('First Post');
    // Syntax highlighting included
    expect(html).toContain('hljs');
    // Tag index pages
    const tagHtml = await fs.readFile(path.join(tmpOut, 'tags', 'news', 'index.html'), 'utf8');
    expect(tagHtml).toContain('Tags');
    // RSS exists
    const rss = await fs.readFile(path.join(tmpOut, 'feed.xml'), 'utf8');
    expect(rss).toContain('<rss');
    expect(Array.from(tags.keys())).toContain('news');
  });
});

describe('CLI flag behavior (drafts, live reload)', () => {
  it('includes drafts when includeDrafts = true', async () => {
    await fs.rm(tmpOut, { recursive: true, force: true });
    const { pages } = await buildSite({
      srcDir: path.join(fixtures, 'src'),
      templatesDir: path.join(fixtures, 'templates'),
      outDir: tmpOut,
      includeDrafts: true,
      clean: true
    });
    expect(pages.find(p => p.relPath === 'draft.md')).toBeTruthy();
  });
});

describe('dev server', () => {
  let stop: null | (() => Promise<void>) = null;
  afterAll(async () => { if (stop) await stop(); });

  it('serves with live reload script emitted', async () => {
    await fs.rm(tmpOut, { recursive: true, force: true });
    const srv = await startDevServer({
      srcDir: path.join(fixtures, 'src'),
      templatesDir: path.join(fixtures, 'templates'),
      outDir: tmpOut,
      includeDrafts: true,
      port: 5599,
      clean: true
    } as any);
    stop = srv.stop;
    const html = await fs.readFile(path.join(tmpOut, 'post1.html'), 'utf8');
    expect(html).toContain('/_livereload.js');
  });
});
