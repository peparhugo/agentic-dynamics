import { generateSite } from '../src/generator';
import { Page } from '../src/types';
import fs from 'fs';
import path from 'path';
import os from 'os';

describe('generateSite', () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  const pages: Page[] = [
    {
      frontmatter: { title: 'Post One', date: '2024-03-01', tags: ['tag1', 'tag2'] },
      html: '<p>Content one</p>',
      slug: 'post-one',
    },
    {
      frontmatter: { title: 'Post Two', date: '2024-01-15', tags: [] },
      html: '<p>Content two</p>',
      slug: 'post-two',
    },
  ];

  it('creates individual page HTML files', () => {
    generateSite(pages, outputDir);

    const postOnePath = path.join(outputDir, 'post-one.html');
    const postTwoPath = path.join(outputDir, 'post-two.html');

    expect(fs.existsSync(postOnePath)).toBe(true);
    expect(fs.existsSync(postTwoPath)).toBe(true);

    const contentOne = fs.readFileSync(postOnePath, 'utf-8');
    expect(contentOne).toContain('Post One');
    expect(contentOne).toContain('Content one');
    expect(contentOne).toContain('2024-03-01');
    expect(contentOne).toContain('tag1');
    expect(contentOne).toContain('tag2');
  });

  it('creates index.html listing all pages', () => {
    generateSite(pages, outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('All Posts');
    expect(content).toContain('Post One');
    expect(content).toContain('Post Two');
    expect(content).toContain('post-one.html');
    expect(content).toContain('post-two.html');
  });

  it('handles empty pages array', () => {
    generateSite([], outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('All Posts');
  });
});
