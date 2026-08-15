import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import {
  build,
  parseFrontmatter,
  normalizeTags,
  markdownToHtml,
} from '../src';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
}

describe('parseFrontmatter', () => {
  it('strips the --- frontmatter block and parses YAML', () => {
    const raw = `---
title: Hello World
date: 2024-01-01
tags:
  - typescript
  - ssg
---
# Body
This is the body.`;
    const { data, body } = parseFrontmatter(raw);

    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2024-01-01');
    expect(data.tags).toEqual(['typescript', 'ssg']);
    expect(body).not.toContain('---');
    expect(body).toContain('# Body');
  });

  it('returns the raw body when there is no frontmatter', () => {
    const raw = '# Just a heading';
    const { data, body } = parseFrontmatter(raw);
    expect(data).toEqual({});
    expect(body).toBe(raw);
  });
});

describe('normalizeTags', () => {
  it('handles arrays', () => {
    expect(normalizeTags(['a', 'b'])).toEqual(['a', 'b']);
  });

  it('handles comma-separated strings', () => {
    expect(normalizeTags('a, b, c')).toEqual(['a', 'b', 'c']);
  });

  it('handles undefined', () => {
    expect(normalizeTags(undefined)).toEqual([]);
  });
});

describe('markdownToHtml', () => {
  it('converts markdown to HTML', () => {
    const html = markdownToHtml('# Hello');
    expect(html).toContain('<h1>Hello</h1>');
  });
});

describe('build', () => {
  it('generates page files and an index listing all pages', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();

    await fs.writeFile(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello
date: 2024-01-01
tags: [greeting]
---
# Welcome
This is a **test**.`
    );
    await fs.writeFile(
      path.join(contentDir, 'about.md'),
      `---
title: About
date: 2024-02-02
tags:
  - info
  - meta
---
## About us
Some text.`
    );

    const pages = await build({ content: contentDir, output: outputDir });

    expect(pages).toHaveLength(2);

    const helloHtml = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(helloHtml).toContain('<title>Hello</title>');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('<h1>Welcome</h1>');
    expect(helloHtml).not.toContain('---');

    const aboutHtml = await fs.readFile(path.join(outputDir, 'about.html'), 'utf8');
    expect(aboutHtml).toContain('<title>About</title>');
    expect(aboutHtml).toContain('<h2>About us</h2>');

    const indexHtml = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('href="hello.html"');
    expect(indexHtml).toContain('href="about.html"');
    expect(indexHtml).toContain('Hello');
    expect(indexHtml).toContain('About');
  });

  it('handles nested directories and derives slugs', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();

    await fs.mkdir(path.join(contentDir, 'posts'), { recursive: true });
    await fs.writeFile(
      path.join(contentDir, 'posts', 'first.md'),
      '---\ntitle: First Post\n---\n# First'
    );

    const pages = await build({ content: contentDir, output: outputDir });
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('posts/first');

    const pageHtml = await fs.readFile(
      path.join(outputDir, 'posts', 'first.html'),
      'utf8'
    );
    expect(pageHtml).toContain('<title>First Post</title>');
  });

  it('uses the slug as a fallback title when frontmatter omits title', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();

    await fs.writeFile(path.join(contentDir, 'no-title.md'), '# Body only');

    const pages = await build({ content: contentDir, output: outputDir });
    expect(pages[0].title).toBe('no-title');
  });
});
