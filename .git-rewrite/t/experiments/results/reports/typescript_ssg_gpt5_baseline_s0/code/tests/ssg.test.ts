import { describe, it, expect, beforeAll } from 'vitest';
import path from 'path';
import fs from 'fs';
import { buildSite } from '../src/build';
import { serveWithLiveReload } from '../src/server';
import { spawnSync } from 'child_process';

const FIXTURE = path.resolve(__dirname, 'fixtures/site');
const SRC = path.join(FIXTURE, 'src');
const TPL = path.join(FIXTURE, 'templates');
const OUT = path.join(FIXTURE, '.out');

function read(file: string) {
  return fs.readFileSync(file, 'utf8');
}

describe('Static Site Generator', () => {
  beforeAll(() => {
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
  });

  it('parses frontmatter and renders templates with partials and layout', async () => {
    await buildSite({ srcDir: SRC, templatesDir: TPL, outDir: OUT, siteTitle: 'My Site', siteUrl: 'https://example.com' });
    const html = read(path.join(OUT, 'hello.html'));
    expect(html).toContain('<title>Hello World — My Site</title>');
    expect(html).toContain('<header><a href="/">Home</a> — My Site</header>');
    expect(html).toContain('<h1>Hello World</h1>');
    // Syntax highlighting present
    expect(html).toContain('class="hljs');
  });

  it('excludes drafts by default and includes when includeDrafts is true', async () => {
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    await buildSite({ srcDir: SRC, templatesDir: TPL, outDir: OUT, siteTitle: 'My Site', siteUrl: 'https://example.com' });
    expect(fs.existsSync(path.join(OUT, 'draft.html'))).toBe(false);

    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    await buildSite({ srcDir: SRC, templatesDir: TPL, outDir: OUT, includeDrafts: true, siteTitle: 'My Site', siteUrl: 'https://example.com' });
    expect(fs.existsSync(path.join(OUT, 'draft.html'))).toBe(true);
  });

  it('generates tag index pages and RSS feed', async () => {
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    await buildSite({ srcDir: SRC, templatesDir: TPL, outDir: OUT, siteTitle: 'My Site', siteUrl: 'https://example.com' });
    const tagIndex = path.join(OUT, 'tags', 'intro', 'index.html');
    expect(fs.existsSync(tagIndex)).toBe(true);
    const rssPath = path.join(OUT, 'rss.xml');
    expect(fs.existsSync(rssPath)).toBe(true);
    const rss = read(rssPath);
    expect(rss).toContain('<rss');
    expect(rss).toContain('<title>My Site</title>');
  });

  it('serves with live reload and injects client script', async () => {
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    const server = await serveWithLiveReload({ srcDir: SRC, templatesDir: TPL, outDir: OUT, port: 5189, siteTitle: 'My Site', siteUrl: 'https://example.com' });
    const html = read(path.join(OUT, 'hello.html'));
    expect(html).toContain('new WebSocket');
    await server.close();
  });

  it('CLI flag behavior: --include-drafts toggles inclusion', async () => {
    // Build without drafts via CLI
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    const cli = path.resolve(__dirname, '..', 'dist', 'cli.js');
    let res = spawnSync('node', [cli, 'build', '-s', SRC, '-t', TPL, '-o', OUT], { encoding: 'utf8' });
    expect(res.status).toBe(0);
    expect(fs.existsSync(path.join(OUT, 'draft.html'))).toBe(false);

    // Build with drafts via CLI
    fs.rmSync(OUT, { recursive: true, force: true });
    fs.mkdirSync(OUT, { recursive: true });
    res = spawnSync('node', [cli, 'build', '-s', SRC, '-t', TPL, '-o', OUT, '--include-drafts'], { encoding: 'utf8' });
    expect(res.status).toBe(0);
    expect(fs.existsSync(path.join(OUT, 'draft.html'))).toBe(true);
  });
});
