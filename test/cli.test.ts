import { execFile } from 'node:child_process';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

it('builds with custom content and output options', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
  const content = path.join(root, 'posts');
  const output = path.join(root, 'site');
  await fs.mkdir(content);
  await fs.writeFile(path.join(content, 'hello.md'), 'Hello CLI');

  try {
    const cliPath = path.resolve(__dirname, '../lib/cli.js');
    const built = await execFileAsync(process.execPath, [cliPath, 'build', '--content', content, '--output', output]);
    expect(built.stdout).toContain('Generated 1 page');
    expect(await fs.readFile(path.join(output, 'hello.html'), 'utf8')).toContain('Hello CLI');
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

it('reports incremental build statistics', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-incremental-'));
  const content = path.join(root, 'content');
  const output = path.join(root, 'dist');
  await fs.mkdir(content);
  await fs.writeFile(path.join(content, 'hello.md'), 'Hello cache');

  try {
    const cliPath = path.resolve(__dirname, '../lib/cli.js');
    await execFileAsync(process.execPath, [cliPath, 'build', '--content', content, '--output', output, '--incremental']);
    const cached = await execFileAsync(process.execPath, [cliPath, 'build', '--content', content, '--output', output, '--incremental']);
    expect(cached.stdout).toContain('Build stats: 0 built, 1 skipped');

    const clean = await execFileAsync(process.execPath, [cliPath, 'build', '--content', content, '--output', output, '--incremental', '--clean']);
    expect(clean.stdout).toContain('Build stats: 1 built, 0 skipped');
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
