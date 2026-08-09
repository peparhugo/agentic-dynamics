import { describe, it, expect, afterAll } from 'vitest';
import { execSync } from 'node:child_process';
import { existsSync, rmSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const CLI = 'node dist/index.js';
const FIXTURES_DIR = join(__dirname, 'fixtures');
const SOURCE = join(FIXTURES_DIR, 'content');
const TEMPLATES = join(FIXTURES_DIR, 'templates');
const OUTPUT = join(FIXTURES_DIR, 'output');

describe('CLI build command', () => {
  afterAll(() => {
    if (existsSync(OUTPUT)) {
      rmSync(OUTPUT, { recursive: true });
    }
  });

  it('builds site to output directory', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test Site" --url http://example.com`,
      { stdio: 'pipe' },
    );

    expect(existsSync(join(OUTPUT, 'index.html'))).toBe(true);
    expect(existsSync(join(OUTPUT, 'hello-world', 'index.html'))).toBe(true);
  });

  it('excludes drafts by default', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test" --url http://example.com`,
      { stdio: 'pipe' },
    );

    const indexPath = join(OUTPUT, 'index.html');
    const indexContent = readFileSync(indexPath, 'utf-8');
    expect(indexContent).not.toContain('Draft Post');
  });

  it('includes drafts with --drafts flag', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test" --url http://example.com --drafts`,
      { stdio: 'pipe' },
    );

    const indexPath = join(OUTPUT, 'index.html');
    const indexContent = readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('Draft Post');
  });

  it('generates RSS feed', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test" --url http://example.com`,
      { stdio: 'pipe' },
    );

    const feedPath = join(OUTPUT, 'feed.xml');
    expect(existsSync(feedPath)).toBe(true);

    const feedContent = readFileSync(feedPath, 'utf-8');
    expect(feedContent).toContain('<rss version="2.0"');
    expect(feedContent).toContain('<title>Hello World</title>');
    expect(feedContent).not.toContain('Draft Post');
  });

  it('generates tag index pages', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test" --url http://example.com`,
      { stdio: 'pipe' },
    );

    expect(existsSync(join(OUTPUT, 'tags', 'web', 'index.html'))).toBe(true);
    expect(existsSync(join(OUTPUT, 'tags', 'typescript', 'index.html'))).toBe(
      true,
    );
  });

  it('respects --title and --url flags', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Custom Title" --url https://custom.example`,
      { stdio: 'pipe' },
    );

    const indexContent = readFileSync(join(OUTPUT, 'index.html'), 'utf-8');
    expect(indexContent).toContain('Custom Title');

    const feedContent = readFileSync(join(OUTPUT, 'feed.xml'), 'utf-8');
    expect(feedContent).toContain('Custom Title');
    expect(feedContent).toContain('https://custom.example');
  });

  it('sorts posts by date descending', () => {
    if (existsSync(OUTPUT)) rmSync(OUTPUT, { recursive: true });

    execSync(
      `${CLI} build -s ${SOURCE} -t ${TEMPLATES} -o ${OUTPUT} --title "Test" --url http://example.com`,
      { stdio: 'pipe' },
    );

    const indexContent = readFileSync(join(OUTPUT, 'index.html'), 'utf-8');
    const helloIdx = indexContent.indexOf('Hello World');
    const anotherIdx = indexContent.indexOf('Another Post');
    expect(anotherIdx).toBeGreaterThan(helloIdx);
  });
});
