import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/builder';
import { CACHE_FILE_NAME } from '../src/cache';

function tmpdir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incr-'));
}

function setupSite(): {
  root: string;
  content: string;
  output: string;
  templates: string;
} {
  const root = tmpdir();
  const content = path.join(root, 'content');
  const output = path.join(root, 'dist');
  const templates = path.join(root, 'templates');
  fs.mkdirSync(content, { recursive: true });
  fs.mkdirSync(templates, { recursive: true });
  fs.writeFileSync(
    path.join(content, 'alpha.md'),
    '---\ntitle: Alpha\ndate: 2024-01-01\ntags: [a]\n---\n# Alpha\n'
  );
  fs.writeFileSync(
    path.join(content, 'beta.md'),
    '---\ntitle: Beta\ndate: 2024-01-02\n---\n# Beta\n'
  );
  fs.mkdirSync(path.join(content, 'nested'), { recursive: true });
  fs.writeFileSync(
    path.join(content, 'nested', 'gamma.md'),
    '---\ntitle: Gamma\n---\n# Gamma\n'
  );
  fs.writeFileSync(path.join(templates, 'post.hbs'), '<article>{{{content}}}</article>\n');
  return { root, content, output, templates };
}

describe('incremental builds', () => {
  it('performs a full build and writes a cache manifest on first incremental run', () => {
    const { content, output } = setupSite();

    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(result.stats.incremental).toBe(true);

    const cacheFile = path.join(output, CACHE_FILE_NAME);
    expect(fs.existsSync(cacheFile)).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    expect(Object.keys(manifest.pages)).toHaveLength(3);
  });

  it('skips all unchanged pages on a second incremental run', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });
    const before = fs.readFileSync(path.join(output, 'alpha.html'), 'utf8');

    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(3);

    const after = fs.readFileSync(path.join(output, 'alpha.html'), 'utf8');
    expect(after).toBe(before);
  });

  it('rebuilds only the page whose source changed', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });
    const betaBefore = fs.readFileSync(path.join(output, 'beta.html'), 'utf8');

    fs.writeFileSync(
      path.join(content, 'alpha.md'),
      '---\ntitle: Alpha\ndate: 2024-01-01\ntags: [a]\n---\n# Alpha changed\n'
    );

    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(2);

    const alpha = fs.readFileSync(path.join(output, 'alpha.html'), 'utf8');
    expect(alpha).toContain('Alpha changed');

    const betaAfter = fs.readFileSync(path.join(output, 'beta.html'), 'utf8');
    expect(betaAfter).toBe(betaBefore);
  });

  it('rebuilds pages when a template changes', () => {
    const { content, output, templates } = setupSite();

    build({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    fs.writeFileSync(path.join(templates, 'post.hbs'), '<section>{{{content}}}</section>\n');

    const result = build({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('rebuilds pages when a layout/partial template changes', () => {
    const { content, output, templates } = setupSite();
    fs.mkdirSync(path.join(templates, 'layouts'), { recursive: true });
    fs.writeFileSync(
      path.join(templates, 'layouts', 'main.hbs'),
      '<html><body>{{{body}}}</body></html>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    fs.writeFileSync(
      path.join(templates, 'layouts', 'main.hbs'),
      '<html><body><div id="wrap">{{{body}}}</div></body></html>\n'
    );

    const result = build({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('does a clean full build when the cache manifest is missing', () => {
    const { content, output } = setupSite();

    // No cache: incremental falls back to a full build.
    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(fs.existsSync(path.join(output, CACHE_FILE_NAME))).toBe(true);
  });

  it('forces a full rebuild when --clean is passed', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });

    const result = build({
      contentDir: content,
      outputDir: output,
      incremental: true,
      clean: true,
    });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('clears a stale cache entry for a deleted source file', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });

    fs.rmSync(path.join(content, 'beta.md'));

    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.pages).toHaveLength(2);

    const manifest = JSON.parse(
      fs.readFileSync(path.join(output, CACHE_FILE_NAME), 'utf8')
    );
    expect(Object.keys(manifest.pages)).toHaveLength(2);
    expect(manifest.pages.beta).toBeUndefined();
  });

  it('reports time saved when pages are skipped', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });

    const result = build({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
    expect(result.stats.durationMs).toBeGreaterThanOrEqual(0);
  });

  it('caches parsed frontmatter in the manifest', () => {
    const { content, output } = setupSite();

    build({ contentDir: content, outputDir: output, incremental: true });

    const manifest = JSON.parse(
      fs.readFileSync(path.join(output, CACHE_FILE_NAME), 'utf8')
    );
    expect(manifest.pages.alpha.frontmatter.title).toBe('Alpha');
    expect(manifest.pages.alpha.tags).toEqual(['a']);
  });

  it('still produces a plain full build when incremental is not requested', () => {
    const { content, output } = setupSite();

    const result = build({ contentDir: content, outputDir: output });

    expect(result.stats.pagesBuilt).toBe(3);
    expect(result.stats.incremental).toBe(false);
    expect(fs.existsSync(path.join(output, CACHE_FILE_NAME))).toBe(false);
  });
});
