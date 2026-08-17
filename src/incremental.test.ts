import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, CACHE_FILENAME, loadManifest } from './index';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incr-'));
}

function write(file: string, content: string): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}

function makeSite() {
  const content = makeTempDir();
  const output = makeTempDir();
  const templates = makeTempDir();

  write(path.join(content, 'a.md'), '---\ntitle: Alpha\ndate: 2024-01-01\n---\nAlpha body\n');
  write(path.join(content, 'b.md'), '---\ntitle: Beta\n---\nBeta body\n');

  return { content, output, templates };
}

describe('incremental builds', () => {
  it('does a full build when the cache is missing', () => {
    const { content, output, templates } = makeSite();
    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(site.stats.built).toBe(2);
    expect(site.stats.skipped).toBe(0);
    expect(site.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(output, CACHE_FILENAME))).toBe(true);
  });

  it('skips all pages when nothing changed', () => {
    const { content, output, templates } = makeSite();

    const first = buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    expect(first.stats.built).toBe(2);

    const alphaBefore = fs.readFileSync(path.join(output, 'a.html'), 'utf8');
    const betaBefore = fs.readFileSync(path.join(output, 'b.html'), 'utf8');

    const second = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(second.stats.built).toBe(0);
    expect(second.stats.skipped).toBe(2);
    expect(second.pages).toHaveLength(2);
    expect(second.pages.every((p) => p.cached)).toBe(true);

    const alphaAfter = fs.readFileSync(path.join(output, 'a.html'), 'utf8');
    const betaAfter = fs.readFileSync(path.join(output, 'b.html'), 'utf8');
    expect(alphaAfter).toBe(alphaBefore);
    expect(betaAfter).toBe(betaBefore);
  });

  it('rebuilds only the changed source page', () => {
    const { content, output, templates } = makeSite();

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    write(path.join(content, 'b.md'), '---\ntitle: Beta\n---\nBeta body (updated)\n');

    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(site.stats.built).toBe(1);
    expect(site.stats.skipped).toBe(1);

    const alpha = site.pages.find((p) => p.slug === 'a');
    const beta = site.pages.find((p) => p.slug === 'b');
    expect(alpha?.cached).toBe(true);
    expect(beta?.cached).toBeFalsy();

    expect(fs.readFileSync(path.join(output, 'b.html'), 'utf8')).toContain('Beta body (updated)');
  });

  it('rebuilds pages when their template changes', () => {
    const { content, output, templates } = makeSite();

    write(path.join(content, 'special.md'), '---\ntitle: Special\ntemplate: special\n---\nSpecial body\n');
    write(path.join(templates, 'special.hbs'), '<div class="v1">{{{body}}}</div>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    write(path.join(templates, 'special.hbs'), '<div class="v2">{{{body}}}</div>');

    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(site.stats.built).toBe(1);
    expect(site.stats.skipped).toBe(2);

    const special = site.pages.find((p) => p.slug === 'special');
    expect(special?.cached).toBeFalsy();
    expect(fs.readFileSync(path.join(output, 'special.html'), 'utf8')).toContain('<div class="v2">');

    const alpha = site.pages.find((p) => p.slug === 'a');
    expect(alpha?.cached).toBe(true);
  });

  it('--clean forces a full rebuild even when the cache matches', () => {
    const { content, output, templates } = makeSite();

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
      clean: true,
    });

    expect(site.stats.built).toBe(2);
    expect(site.stats.skipped).toBe(0);
  });

  it('rebuilds a page whose rendered output was deleted', () => {
    const { content, output, templates } = makeSite();

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    fs.unlinkSync(path.join(output, 'a.html'));

    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(site.stats.built).toBe(1);
    expect(site.stats.skipped).toBe(1);
    expect(fs.existsSync(path.join(output, 'a.html'))).toBe(true);
  });

  it('picks up newly added files without invalidating existing ones', () => {
    const { content, output, templates } = makeSite();

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    write(path.join(content, 'c.md'), '---\ntitle: Charlie\n---\nCharlie body\n');

    const site = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });

    expect(site.stats.built).toBe(1);
    expect(site.stats.skipped).toBe(2);
    expect(site.pages.map((p) => p.slug).sort()).toEqual(['a', 'b', 'c']);
  });

  it('updates the manifest with fresh hashes after an incremental build', () => {
    const { content, output, templates } = makeSite();

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    write(path.join(content, 'a.md'), '---\ntitle: Alpha\n---\nAlpha body (v2)\n');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    const manifest = loadManifest(path.join(output, CACHE_FILENAME));
    const entry = manifest.pages['a'];
    expect(entry).toBeDefined();
    expect(entry.html).toContain('Alpha body (v2)');

    const stable = buildSite({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental: true,
    });
    expect(stable.stats.skipped).toBe(2);
    expect(stable.stats.built).toBe(0);
  });

  it('produces identical output for incremental and clean builds', () => {
    const base = makeSite();
    write(path.join(base.content, 'nested', 'deep.md'), '---\ntitle: Deep\n---\nDeep body\n');

    buildSite({ contentDir: base.content, outputDir: base.output, templatesDir: base.templates });

    const incrOut = makeTempDir();
    const site = buildSite({
      contentDir: base.content,
      outputDir: incrOut,
      templatesDir: base.templates,
      incremental: true,
    });
    expect(site.stats.built).toBe(3);

    const readAll = (dir: string): string[] => {
      const out: string[] = [];
      for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) =>
        a.name.localeCompare(b.name)
      )) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          out.push(...readAll(full));
        } else {
          out.push(fs.readFileSync(full, 'utf8'));
        }
      }
      return out;
    };

    expect(readAll(incrOut)).toEqual(readAll(base.output));
  });
});
