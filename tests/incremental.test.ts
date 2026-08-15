import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  build,
  buildIncremental,
  BuildCache,
  hashString,
  computeTemplateHash,
  buildPage,
} from '../src';

function tmp(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content);
  }
}

const A = '---\ntitle: A\ndate: 2024-01-01\n---\n# A\n';
const B = '---\ntitle: B\ndate: 2024-02-01\n---\n# B\n';

describe('buildIncremental', () => {
  it('builds all pages on first incremental build and writes a manifest', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });

      expect(result.stats.totalPages).toBe(2);
      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
      expect(fs.existsSync(path.join(out, '.ssg-cache.json'))).toBe(true);
      expect(fs.existsSync(path.join(out, 'a.html'))).toBe(true);
      expect(fs.existsSync(path.join(out, 'b.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('skips all pages when nothing changed', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });

      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });
      const aBefore = fs.readFileSync(path.join(out, 'a.html'), 'utf-8');

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(0);
      expect(result.stats.pagesSkipped).toBe(2);
      expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
      expect(fs.readFileSync(path.join(out, 'a.html'), 'utf-8')).toBe(aBefore);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('rebuilds only the changed page', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });
      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });

      fs.writeFileSync(
        path.join(content, 'a.md'),
        '---\ntitle: A\ndate: 2024-01-01\n---\n# A changed\n'
      );

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);
      expect(fs.readFileSync(path.join(out, 'a.html'), 'utf-8')).toContain('A changed');
      expect(fs.readFileSync(path.join(out, 'b.html'), 'utf-8')).toContain('B');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('rebuilds pages whose template changed but not others', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, {
        'a.md': '---\ntitle: A\ndate: 2024-01-01\ntemplate: fancy\n---\n# A\n',
        'b.md': B,
      });
      writeContent(tpl, { 'fancy.hbs': '<main>{{title}}</main>' });

      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });

      fs.writeFileSync(path.join(tpl, 'fancy.hbs'), '<main class="v2">{{title}}</main>');

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);
      expect(fs.readFileSync(path.join(out, 'a.html'), 'utf-8')).toContain('class="v2"');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('performs a clean rebuild when clean flag is passed', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });
      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
        clean: true,
      });

      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('rebuilds a page whose output file is missing', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });
      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });

      fs.rmSync(path.join(out, 'b.html'));

      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);
      expect(fs.existsSync(path.join(out, 'b.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });
});

describe('cache manifest', () => {
  it('tracks source and template hashes', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A });
      buildIncremental({ contentDir: content, outputDir: out, templatesDir: tpl, incremental: true });

      const manifest = JSON.parse(fs.readFileSync(path.join(out, '.ssg-cache.json'), 'utf-8'));
      expect(Object.keys(manifest.pages)).toEqual(['a']);
      expect(manifest.pages.a.sourceHash).toBe(hashString(A));
      expect(typeof manifest.pages.a.templateHash).toBe('string');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('is not required for a clean build (missing cache triggers full build)', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    const tpl = tmp('ssg-inc-tpl-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });
      // no prior build -> cache missing -> full build
      const result = buildIncremental({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        incremental: true,
      });
      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });
});

describe('BuildCache', () => {
  it('caches parsed frontmatter and invalidates on demand', () => {
    const dir = tmp('ssg-inc-cache-');
    const cacheFile = path.join(dir, '.ssg-cache.json');
    try {
      const cache = new BuildCache(cacheFile);
      expect(cache.getFrontmatter('a')).toBeUndefined();

      cache.setEntry({
        slug: 'a',
        sourceHash: 'h1',
        templateHash: 't1',
        frontmatter: { title: 'A', tags: ['x'] },
        bodyHtml: '<p>body</p>',
      });
      cache.save();

      expect(cache.getFrontmatter('a')?.title).toBe('A');
      expect(cache.getHtml('a')).toBeUndefined();
      cache.setHtml('a', '<html>A</html>');
      expect(cache.getHtml('a')).toBe('<html>A</html>');

      // reload from disk to verify persistence of frontmatter
      const reloaded = new BuildCache(cacheFile);
      expect(reloaded.getFrontmatter('a')?.title).toBe('A');

      cache.invalidate('a');
      expect(cache.getEntry('a')).toBeUndefined();
      expect(cache.getFrontmatter('a')).toBeUndefined();
      expect(cache.getHtml('a')).toBeUndefined();
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('computeTemplateHash', () => {
  it('changes when the template source changes', () => {
    const tpl = tmp('ssg-inc-tpl-');
    try {
      fs.writeFileSync(path.join(tpl, 'fancy.hbs'), '<main>{{title}}</main>');
      const page = buildPage('a', '---\ntitle: A\ntemplate: fancy\n---\n# A\n');

      const h1 = computeTemplateHash(tpl, page);
      fs.writeFileSync(path.join(tpl, 'fancy.hbs'), '<main class="v2">{{title}}</main>');
      const h2 = computeTemplateHash(tpl, page);

      expect(h1).not.toBe(h2);
    } finally {
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });
});

describe('build (non-incremental) regression', () => {
  it('still returns pages sorted by date', () => {
    const content = tmp('ssg-inc-content-');
    const out = tmp('ssg-inc-out-');
    try {
      writeContent(content, { 'a.md': A, 'b.md': B });
      const pages = build({ contentDir: content, outputDir: out });
      expect(pages.map((p) => p.slug)).toEqual(['b', 'a']);
      expect(fs.existsSync(path.join(out, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
    }
  });
});
