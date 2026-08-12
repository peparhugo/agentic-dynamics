import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export interface Fixture {
  root: string;
  contentDir: string;
  outputDir: string;
}

export function createFixture(files: Record<string, string>): Fixture {
  const root = mkdtempSync(join(tmpdir(), 'ssg-'));
  const contentDir = join(root, 'content');
  const outputDir = join(root, 'dist');
  mkdirSync(contentDir, { recursive: true });
  for (const [relativePath, contents] of Object.entries(files)) {
    const fullPath = join(contentDir, relativePath);
    mkdirSync(join(fullPath, '..'), { recursive: true });
    writeFileSync(fullPath, contents, 'utf8');
  }
  return { root, contentDir, outputDir };
}

export function cleanupFixture(fixture: Fixture): void {
  rmSync(fixture.root, { recursive: true, force: true });
}
