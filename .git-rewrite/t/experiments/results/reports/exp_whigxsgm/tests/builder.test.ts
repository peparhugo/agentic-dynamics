import { describe, it, expect, beforeAll } from 'vitest';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { buildSite } from '../src/builder';

function tmpDir(prefix: string) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function copyDir(src: string, dest: string) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of entries) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

describe('buildSite', () => {
  const fxRoot = path.join(__dirname, 'fixtures');
  let work: string;
  let srcDir: string;
  let templatesDir: string;
  let outDir: string;

  beforeAll(() => {
    work = tmpDir('ssg-test-');
    srcDir = path.join(work, 'content');
    templatesDir = path.join(work, 'templates');
    outDir = path.join(work, 'public');
    copyDir(path.join(fxRoot, 'content'), srcDir);
    copyDir(path.join(fxRoot, 'templates'), templatesDir);
    fs.mkdirSync(outDir, { recursive: true });
  });

  it('parses frontmatter and renders pages with layouts', async () => {
    const site = await buildSite({ srcDir, templatesDir, outDir, siteTitle: 'Test Site', siteUrl: 'https://example.com', dev: false });

    // index
    const indexHtml = fs.readFileSync(path.join(outDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('<title>Home – Test Site</title>');
    expect(indexHtml).toContain('<h1>Home</h1>');
    // code block highlighted
    expect(indexHtml).toContain('class="hljs');

    // post
    const postHtml = fs.readFileSync(path.join(outDir, 'posts', 'first-post.html'), 'utf8');
    expect(postHtml).toContain('<h1>First Post</h1>');
    // draft should not be generated
    expect(fs.existsSync(path.join(outDir, 'posts', 'draft-post.html'))).toBe(false);

    // tag page exists and lists the post
    const tagHtml = fs.readFileSync(path.join(outDir, 'tags', 'news', 'index.html'), 'utf8');
    expect(tagHtml).toContain('Tag: news');
    expect(tagHtml).toContain('First Post');

    // rss exists
    const rss = fs.readFileSync(path.join(outDir, 'rss.xml'), 'utf8');
    expect(rss).toContain('<rss');
    expect(rss).toContain('<title>Test Site</title>');
    expect(rss).toContain('<item>');

    // site model
    expect(site.posts.length).toBe(1);
    expect(site.tags.get('news')?.length).toBe(1);
  });
});
