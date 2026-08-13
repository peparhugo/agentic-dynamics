import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from '../src/cli';

describe('CLI', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('builds using custom content and output directories', async () => {
    const temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const contentDir = path.join(temporaryDirectory, 'posts');
    const outputDir = path.join(temporaryDirectory, 'public');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), '# Post');
    const log = jest.spyOn(console, 'log').mockImplementation();

    try {
      await run(['build', '--content', contentDir, '--output', outputDir]);
      await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8')).resolves.toContain('<h1>Post</h1>');
      expect(log).toHaveBeenCalledWith('Generated 1 page.');
    } finally {
      await fs.rm(temporaryDirectory, { recursive: true, force: true });
    }
  });

  it('rejects unsupported commands', async () => {
    await expect(run(['serve'])).rejects.toThrow('Unknown command: serve');
  });
});
