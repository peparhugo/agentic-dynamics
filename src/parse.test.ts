import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseMarkdown } from './parse';

function writeTemp(dir: string, name: string, content: string): string {
  const p = path.join(dir, name);
  fs.writeFileSync(p, content, 'utf-8');
  return p;
}

describe('parseMarkdown', () => {
  let dir: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-parse-'));
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('parses body and slug from a markdown file', () => {
    const file = writeTemp(dir, 'hello-world.md', '# Hello\n\nSome **bold** text.');
    const page = parseMarkdown(file);

    expect(page.slug).toBe('hello-world');
    expect(page.html).toContain('<h1>Hello</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
    expect(page.data.title).toBeUndefined();
  });

  it('parses frontmatter title, date, and tags', () => {
    const file = writeTemp(
      dir,
      'post.md',
      '---\ntitle: My First Post\ndate: 2024-01-02\ntags:\n  - typescript\n  - ssg\n---\n\nBody text.'
    );
    const page = parseMarkdown(file);

    expect(page.data.title).toBe('My First Post');
    expect(page.data.date).toBe('2024-01-02');
    expect(page.data.tags).toEqual(['typescript', 'ssg']);
    expect(page.html).toContain('<p>Body text.</p>');
  });

  it('parses tags as a comma-separated string', () => {
    const file = writeTemp(dir, 'c.md', '---\ntags: alpha, beta\n---\n\nx');
    const page = parseMarkdown(file);
    expect(page.data.tags).toEqual(['alpha', 'beta']);
  });

  it('produces a safe slug from tricky filenames', () => {
    const file = writeTemp(dir, 'My  Article--Name.md', '---\n---\n\nx');
    const page = parseMarkdown(file);
    expect(page.slug).toBe('my-article-name');
  });
});
