import { describe, it, expect } from 'vitest';
import { execSync } from 'node:child_process';
import { join } from 'node:path';
import {
  mkdtemp,
  rm,
  readFile,
  writeFile,
  mkdir,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';

const cliPath = join(import.meta.dirname, '..', 'src', 'index.ts');
const fixturesDir = join(import.meta.dirname, 'fixtures');

function run(args: string): string {
  return execSync(
    `npx tsx ${cliPath} ${args}`,
    { encoding: 'utf-8', env: { ...process.env } },
  );
}

describe('CLI', () => {
  it('requires --source, --templates, and --output', () => {
    expect(() => run('--source src --templates tmpl')).toThrow();
  });

  it('builds site with required flags', async () => {
    const outDir = await mkdtemp(join(tmpdir(), 'ssg-cli-'));
    try {
      const source = join(fixturesDir, 'source');
      const templates = join(fixturesDir, 'templates');

      const output = run(
        `-s ${source} -t ${templates} -o ${outDir} --site-title "CLI Test"`,
      );
      expect(output).toContain('Built');

      const index = await readFile(join(outDir, 'index.html'), 'utf-8');
      expect(index).toContain('CLI Test');
      expect(index).toContain('First Post');
    } finally {
      await rm(outDir, { recursive: true, force: true });
    }
  });

  it('generates RSS when --site-url is provided', async () => {
    const outDir = await mkdtemp(join(tmpdir(), 'ssg-cli-'));
    try {
      const source = join(fixturesDir, 'source');
      const templates = join(fixturesDir, 'templates');

      run(
        `-s ${source} -t ${templates} -o ${outDir} --site-url "https://example.com"`,
      );

      const feed = await readFile(join(outDir, 'feed.xml'), 'utf-8');
      expect(feed).toContain('<rss version="2.0"');
    } finally {
      await rm(outDir, { recursive: true, force: true });
    }
  });

  it('accepts short flags', async () => {
    const outDir = await mkdtemp(join(tmpdir(), 'ssg-cli-'));
    try {
      const source = join(fixturesDir, 'source');
      const templates = join(fixturesDir, 'templates');

      const output = run(`-s ${source} -t ${templates} -o ${outDir}`);
      expect(output).toContain('Built');
    } finally {
      await rm(outDir, { recursive: true, force: true });
    }
  });

  it('--version prints version', () => {
    const output = execSync(`npx tsx ${cliPath} --version`, {
      encoding: 'utf-8',
    });
    expect(output.trim()).toBe('1.0.0');
  });
});
