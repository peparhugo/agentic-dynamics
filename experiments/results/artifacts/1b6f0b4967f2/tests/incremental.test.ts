import fs from 'fs';
import path from 'path';
import os from 'os';
import { build, BuildResult } from '../src/ssg';
import { CacheManager, CacheManifest } from '../src/cache';

function makeTempDir(prefix: string): string {
  const dir = path.join(os.tmpdir(), `${prefix}-${Date.now()}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function cleanup(dir: string): void {
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true });
  }
}

function writePage(dir: string, filename: string, frontmatter: Record<string, any>, body: string): void {
  const lines = ['---'];
  for (const [k, v] of Object.entries(frontmatter)) {
    if (Array.isArray(v)) {
      lines.push(`${k}:`);
      for (const item of v) {
        lines.push(`  - ${item}`);
      }
    } else {
      lines.push(`${k}: ${v}`);
    }
  }
  lines.push('---');
  lines.push('');
  lines.push(body);
  fs.writeFileSync(path.join(dir, filename), lines.join('\n'), 'utf-8');
}

function writeTemplate(dir: string, name: string, content: string): void {
  fs.writeFileSync(path.join(dir, name), content, 'utf-8');
}

describe('SSG incremental builds', () => {
  let contentDir: string;
  let outputDir: string;
  let templateDir: string;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-incr-content');
    outputDir = makeTempDir('ssg-incr-output');
    templateDir = makeTempDir('ssg-incr-templates');
  });

  afterEach(() => {
    cleanup(contentDir);
    cleanup(outputDir);
    cleanup(templateDir);
  });

  describe('basic incremental behavior', () => {
    test('first incremental build builds all pages', () => {
      writePage(contentDir, 'page1.md', { title: 'Page One' }, '# Page One\n\nContent one.');
      writePage(contentDir, 'page2.md', { title: 'Page Two' }, '# Page Two\n\nContent two.');

      const result = build({
        contentDir,
        outputDir,
        templateDir,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
      expect(fs.existsSync(path.join(outputDir, 'page1.html'))).toBe(true);
      expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
      expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    });

    test('second incremental build with no changes skips all pages', () => {
      writePage(contentDir, 'page1.md', { title: 'Page One' }, '# Page One\n\nContent one.');
      writePage(contentDir, 'page2.md', { title: 'Page Two' }, '# Page Two\n\nContent two.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      const result2 = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result2.stats.pagesBuilt).toBe(0);
      expect(result2.stats.pagesSkipped).toBe(2);
    });

    test('modifying one file rebuilds only that page', () => {
      writePage(contentDir, 'page1.md', { title: 'Page One' }, '# Page One\n\nContent one.');
      writePage(contentDir, 'page2.md', { title: 'Page Two' }, '# Page Two\n\nContent two.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      writePage(contentDir, 'page1.md', { title: 'Page One Updated' }, '# Page One\n\nUpdated content.');

      const result2 = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result2.stats.pagesBuilt).toBe(1);
      expect(result2.stats.pagesSkipped).toBe(1);

      const page1Content = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(page1Content).toContain('Page One Updated');
      expect(page1Content).toContain('Updated content.');
    });

    test('modifying a template rebuilds all pages', () => {
      writeTemplate(templateDir, 'default.hbs', '<main><h2>{{title}}</h2>{{{content}}}</main>');
      writePage(contentDir, 'page1.md', { title: 'Page One' }, 'Content one.');
      writePage(contentDir, 'page2.md', { title: 'Page Two' }, 'Content two.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      const page1Before = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(page1Before).toContain('<h2>Page One</h2>');

      writeTemplate(templateDir, 'default.hbs', '<main><h3>{{title}}</h3>{{{content}}}</main>');

      const result2 = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result2.stats.pagesBuilt).toBe(2);
      expect(result2.stats.pagesSkipped).toBe(0);

      const page1Content = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(page1Content).toContain('<h3>Page One</h3>');
      expect(page1Content).not.toContain('<h2>Page One</h2>');
    });

    test('adding a new page builds only the new page', () => {
      writePage(contentDir, 'page1.md', { title: 'Page One' }, '# Page One\n\nContent one.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      writePage(contentDir, 'page2.md', { title: 'Page Two' }, '# Page Two\n\nContent two.');

      const result2 = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result2.stats.pagesBuilt).toBe(1);
      expect(result2.stats.pagesSkipped).toBe(1);
      expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);

      const page2Content = fs.readFileSync(path.join(outputDir, 'page2.html'), 'utf-8');
      expect(page2Content).toContain('Page Two');
    });

    test('removing a source file removes cache entry for that page', () => {
      writePage(contentDir, 'page1.md', { title: 'Page One' }, '# Page One\n\nContent one.');
      writePage(contentDir, 'page2.md', { title: 'Page Two' }, '# Page Two\n\nContent two.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      fs.unlinkSync(path.join(contentDir, 'page2.md'));

      const result2 = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result2.stats.pagesBuilt).toBe(0);
      expect(result2.stats.pagesSkipped).toBe(1);
    });
  });

  describe('cache file management', () => {
    test('cache file is created after incremental build', () => {
      writePage(contentDir, 'page1.md', { title: 'Test' }, '# Test\n\nContent.');

      const cachePath = path.join(outputDir, '.ssg-cache.json');
      expect(fs.existsSync(cachePath)).toBe(false);

      build({ contentDir, outputDir, templateDir, incremental: true });

      expect(fs.existsSync(cachePath)).toBe(true);
      const manifest = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      expect(manifest.pages).toBeDefined();
      expect(manifest.pages['page1']).toBeDefined();
      expect(manifest.pages['page1'].sourceHash).toBeDefined();
      expect(manifest.pages['page1'].templateName).toBe('default');
      expect(manifest.pages['page1'].layoutName).toBe('default');
      expect(manifest.templatesHash).toBeDefined();
    });

    test('cache is updated after content change', () => {
      writePage(contentDir, 'page1.md', { title: 'v1' }, '# v1\n\nContent.');
      build({ contentDir, outputDir, templateDir, incremental: true });

      const cachePath = path.join(outputDir, '.ssg-cache.json');
      const manifest1 = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      const hash1 = manifest1.pages['page1'].sourceHash;

      writePage(contentDir, 'page1.md', { title: 'v2' }, '# v2\n\nContent changed.');
      build({ contentDir, outputDir, templateDir, incremental: true });

      const manifest2 = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      const hash2 = manifest2.pages['page1'].sourceHash;

      expect(hash2).not.toBe(hash1);
    });

    test('--clean flag forces full rebuild and deletes cache', () => {
      writePage(contentDir, 'page1.md', { title: 'Test' }, '# Test\n\nContent.');

      build({ contentDir, outputDir, templateDir, incremental: true });

      const cachePath = path.join(outputDir, '.ssg-cache.json');
      expect(fs.existsSync(cachePath)).toBe(true);

      const result = build({
        contentDir,
        outputDir,
        templateDir,
        incremental: true,
        clean: true,
      });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(0);

      const manifest = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      expect(manifest.pages['page1']).toBeDefined();
    });

    test('non-incremental build does not use caching', () => {
      writePage(contentDir, 'page1.md', { title: 'Test' }, '# Test\n\nContent.');

      const cachePath = path.join(outputDir, '.ssg-cache.json');
      build({ contentDir, outputDir, templateDir });

      expect(fs.existsSync(cachePath)).toBe(false);
    });
  });

  describe('build stats reporting', () => {
    test('reports correct stats for full build', () => {
      writePage(contentDir, 'page1.md', { title: 'A' }, '# A');
      writePage(contentDir, 'page2.md', { title: 'B' }, '# B');
      writePage(contentDir, 'page3.md', { title: 'C' }, '# C');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(3);
      expect(result.stats.pagesSkipped).toBe(0);
    });

    test('reports correct stats with mix of built and skipped', () => {
      writePage(contentDir, 'page1.md', { title: 'A' }, '# A');
      writePage(contentDir, 'page2.md', { title: 'B' }, '# B');
      writePage(contentDir, 'page3.md', { title: 'C' }, '# C');

      build({ contentDir, outputDir, templateDir, incremental: true });

      writePage(contentDir, 'page2.md', { title: 'B Updated' }, '# B updated');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(2);
    });
  });

  describe('incremental with frontmatter templates', () => {
    test('changing frontmatter template triggers rebuild', () => {
      writeTemplate(templateDir, 'custom.hbs', '<div class="custom">{{title}}: {{{content}}}</div>');
      writePage(contentDir, 'page1.md', { title: 'P1', template: 'custom' }, '# P1 content');
      writePage(contentDir, 'page2.md', { title: 'P2' }, '# P2 content');

      build({ contentDir, outputDir, templateDir, incremental: true });

      writePage(contentDir, 'page1.md', { title: 'P1', template: 'default' }, '# P1 content');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);

      const page1Content = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(page1Content).not.toContain('class="custom"');
    });

    test('changing frontmatter layout triggers rebuild', () => {
      writePage(contentDir, 'page1.md', { title: 'P1' }, '# P1');
      writePage(contentDir, 'page2.md', { title: 'P2' }, '# P2');

      build({ contentDir, outputDir, templateDir, incremental: true });

      writePage(contentDir, 'page1.md', { title: 'P1', layout: 'custom' }, '# P1');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);
    });
  });

  describe('edge cases', () => {
    test('incremental with empty content directory', () => {
      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(0);
      expect(result.stats.pagesSkipped).toBe(0);
      expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    });

    test('incremental is idempotent', () => {
      writePage(contentDir, 'page1.md', { title: 'Test' }, '# Test content');

      const r1 = build({ contentDir, outputDir, templateDir, incremental: true });
      expect(r1.stats.pagesBuilt).toBe(1);
      expect(r1.stats.pagesSkipped).toBe(0);

      const r2 = build({ contentDir, outputDir, templateDir, incremental: true });
      expect(r2.stats.pagesBuilt).toBe(0);
      expect(r2.stats.pagesSkipped).toBe(1);

      const r3 = build({ contentDir, outputDir, templateDir, incremental: true });
      expect(r3.stats.pagesBuilt).toBe(0);
      expect(r3.stats.pagesSkipped).toBe(1);
    });

    test('build works with no templates directory', () => {
      const noTemplateDir = path.join(os.tmpdir(), `ssg-no-templates-${Date.now()}`);

      writePage(contentDir, 'page1.md', { title: 'Test' }, '# Test');

      const result = build({
        contentDir,
        outputDir,
        templateDir: noTemplateDir,
        incremental: true,
      });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(fs.existsSync(path.join(outputDir, 'page1.html'))).toBe(true);
    });

    test('build with partials in templates tracks hash changes', () => {
      const partialsDir = path.join(templateDir, 'partials');
      fs.mkdirSync(partialsDir, { recursive: true });
      fs.writeFileSync(path.join(templateDir, 'default.hbs'), '<main>{{> header}}{{title}}{{{content}}}{{> footer}}</main>');
      fs.writeFileSync(path.join(partialsDir, 'header.hbs'), '<header>HEAD</header>');
      fs.writeFileSync(path.join(partialsDir, 'footer.hbs'), '<footer>FOOT</footer>');

      writePage(contentDir, 'page1.md', { title: 'P1' }, '# P1 content');

      build({ contentDir, outputDir, templateDir, incremental: true });

      fs.writeFileSync(path.join(partialsDir, 'header.hbs'), '<header>NEW HEAD</header>');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(0);

      const content = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(content).toContain('NEW HEAD');
    });

    test('layout templates in subdirectory trigger rebuild', () => {
      const layoutsDir = path.join(templateDir, 'layouts');
      fs.mkdirSync(layoutsDir, { recursive: true });
      fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), '<!DOCTYPE html><html><body>{{{body}}}</body></html>');
      fs.writeFileSync(path.join(layoutsDir, 'alt.hbs'), '<!DOCTYPE html><html><body class="alt">{{{body}}}</body></html>');

      writePage(contentDir, 'page1.md', { title: 'P1', layout: 'alt' }, '# Alt layout');

      build({ contentDir, outputDir, templateDir, incremental: true });

      fs.writeFileSync(path.join(layoutsDir, 'alt.hbs'), '<!DOCTYPE html><html><body class="alt-v2">{{{body}}}</body></html>');

      const result = build({ contentDir, outputDir, templateDir, incremental: true });

      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(0);

      const content = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
      expect(content).toContain('alt-v2');
    });
  });
});
