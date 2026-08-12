import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseMarkdownFile } from '../src/parser';

function makeTempFile(content: string, name = 'page.md'): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content, 'utf8');
  return filePath;
}

describe('parseMarkdownFile', () => {
  it('parses frontmatter and renders markdown to HTML', () => {
    const file = makeTempFile(
      `---
title: My Page
date: 2024-03-01
tags: [a, b]
---

Hello **world**`
    );
    const page = parseMarkdownFile(file);

    expect(page.title).toBe('My Page');
    expect(page.date).toBe('2024-03-01');
    expect(page.tags).toEqual(['a', 'b']);
    expect(page.html).toContain('<strong>world</strong>');
    expect(page.html).toContain('Hello');
    expect(page.sourcePath).toBe(file);
  });

  it('falls back to filename for title when frontmatter is missing', () => {
    const file = makeTempFile('Just body text.', 'no-title.md');
    const page = parseMarkdownFile(file);

    expect(page.title).toBe('no-title');
    expect(page.date).toBe('');
    expect(page.tags).toEqual([]);
  });

  it('supports comma-separated tags', () => {
    const file = makeTempFile(
      `---
tags: alpha, beta
---
Body.`
    );
    const page = parseMarkdownFile(file);
    expect(page.tags).toEqual(['alpha', 'beta']);
  });

  it('computes a slug from the relative file path', () => {
    const file = makeTempFile('Body.', 'about.md');
    const page = parseMarkdownFile(file);
    expect(page.slug).toBe('about');
  });

  it('extracts template and layout from frontmatter', () => {
    const file = makeTempFile(
      `---
title: T
template: post
layout: wide
---
Body.`
    );
    const page = parseMarkdownFile(file);
    expect(page.template).toBe('post');
    expect(page.layout).toBe('wide');
  });

  it('omits template and layout when not provided', () => {
    const file = makeTempFile('Body.');
    const page = parseMarkdownFile(file);
    expect(page.template).toBeUndefined();
    expect(page.layout).toBeUndefined();
  });
});
