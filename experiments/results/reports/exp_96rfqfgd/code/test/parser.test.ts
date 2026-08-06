import { describe, it, expect } from 'vitest';
import { parseMarkdownFiles, parseFile } from '../src/parser.js';
import { join } from 'node:path';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { sep } from 'node:path';

describe('parseMarkdownFiles', () => {
  const fixtures = join(import.meta.dirname, 'fixtures', 'source');

  it('parses markdown files and extracts frontmatter', async () => {
    const pages = await parseMarkdownFiles(fixtures);
    expect(pages.length).toBe(2); // draft is excluded

    const post1 = pages.find((p) => p.frontmatter.title === 'First Post');
    expect(post1).toBeDefined();
    expect(post1!.frontmatter.date).toBe('2024-01-15');
    expect(post1!.frontmatter.tags).toEqual(['javascript', 'tutorial']);
    expect(post1!.url).toBe('/post1.html');

    const post2 = pages.find((p) => p.frontmatter.title === 'Second Post');
    expect(post2).toBeDefined();
    expect(post2!.frontmatter.tags).toEqual(['typescript', 'tutorial']);
    expect(post2!.url).toBe('/post2.html');
  });

  it('excludes draft posts', async () => {
    const pages = await parseMarkdownFiles(fixtures);
    const drafts = pages.filter((p) => p.frontmatter.draft === true);
    expect(drafts.length).toBe(0);
  });

  it('converts markdown to HTML', async () => {
    const pages = await parseMarkdownFiles(fixtures);
    const post1 = pages.find((p) => p.frontmatter.title === 'First Post')!;
    expect(post1.html).toContain('<h1>Hello World</h1>');
    expect(post1.html).toContain(
      '<pre><code class="language-javascript">',
    );
  });

  it('preserves raw content and frontmatter', async () => {
    const pages = await parseMarkdownFiles(fixtures);
    const post2 = pages.find((p) => p.frontmatter.title === 'Second Post')!;
    expect(post2.content).toContain('# Another Post');
    expect(post2.frontmatter.title).toBe('Second Post');
    expect(post2.frontmatter.date).toBe('2024-02-20');
  });
});

describe('parseFile', () => {
  it('returns null for draft files', async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), 'ssg-test-'));
    try {
      const filePath = join(tmpDir, 'draft.md');
      await writeFile(
        filePath,
        '---\ntitle: Draft\ndraft: true\n---\nContent',
      );
      const result = await parseFile(filePath, tmpDir);
      expect(result).toBeNull();
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  it('handles files without frontmatter', async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), 'ssg-test-'));
    try {
      const filePath = join(tmpDir, 'plain.md');
      await writeFile(filePath, '# Just content');
      const result = await parseFile(filePath, tmpDir);
      expect(result).not.toBeNull();
      expect(result!.frontmatter.title).toBeUndefined();
      expect(result!.html).toContain('<h1>Just content</h1>');
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  it('computes correct URL from path', async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), 'ssg-test-'));
    try {
      const filePath = join(tmpDir, 'blog', 'hello.md');
      await mkdtemp(join(tmpDir, 'blog'));
      // need to create the directory structure first
      await writeFile(
        filePath,
        '---\ntitle: Hello\n---\nContent',
        { flag: 'w' },
      );
      const result = await parseFile(filePath, tmpDir);
      expect(result).not.toBeNull();
      // URL should use forward slashes
      expect(result!.url).toBe('/blog/hello.html');
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });
});
