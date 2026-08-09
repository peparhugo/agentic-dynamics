import { describe, it, expect, beforeAll } from 'vitest';
import path from 'node:path';
import fs from 'node:fs/promises';
import { generateSite } from '../src/generator';

const fixtures = path.resolve('tests/fixtures');
const srcDir = path.join(fixtures, 'content');
const templatesDir = path.join(fixtures, 'templates');
const outDir = path.resolve('tests/tmp-out');

describe('site generation', () => {
  beforeAll(async () => {
    await fs.rm(outDir, { recursive: true, force: true });
  });

  it('renders markdown with frontmatter, templates, tags, and rss', async () => {
    const { pages, tags } = await generateSite({ srcDir, templatesDir, outDir, includeDrafts: false, siteUrl: 'https://example.com' });
    expect(pages.length).toBe(1); // draft excluded
    const html = await fs.readFile(path.join(outDir, 'post1', 'index.html'), 'utf8');
    expect(html).toContain('<h2>First Post</h2>');
    expect(html).toContain("class=\"hljs language-js\"");
    // tag index
    const tagIndex = await fs.readFile(path.join(outDir, 'tags', 'index.html'), 'utf8');
    expect(tagIndex).toContain('/tags/intro/');
    // tag page
    const tagPage = await fs.readFile(path.join(outDir, 'tags', 'intro', 'index.html'), 'utf8');
    expect(tagPage).toContain('First Post');
    // rss
    const rss = await fs.readFile(path.join(outDir, 'rss.xml'), 'utf8');
    expect(rss).toContain('<rss');
    expect(rss).toContain('<item>');
    expect(rss).toContain('<link>https://example.com/post1/</link>');
  });

  it('includes drafts when includeDrafts is true', async () => {
    await fs.rm(outDir, { recursive: true, force: true });
    const { pages } = await generateSite({ srcDir, templatesDir, outDir, includeDrafts: true });
    expect(pages.find(p => p.fm.title === 'Draft Post')).toBeTruthy();
    const html = await fs.readFile(path.join(outDir, 'draft-post', 'index.html'), 'utf8');
    expect(html).toContain('Draft Post');
  });
});
