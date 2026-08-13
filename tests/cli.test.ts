import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

test('CLI accepts custom content and output directories', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
  const contentDir = path.join(root, 'articles');
  const outputDir = path.join(root, 'public');

  try {
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), '# CLI content');

    const result = await execFileAsync(process.execPath, [
      path.resolve('lib/cli.js'),
      'build',
      '--content', contentDir,
      '--output', outputDir
    ]);

    expect(result.stdout).toContain('Generated 1 page');
    await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8')).resolves.toContain('<h1>CLI content</h1>');
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
