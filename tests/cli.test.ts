import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from '../src/cli';

describe('CLI', () => {
  it('builds using custom content and output directories', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'posts');
    const output = path.join(root, 'public');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    try {
      await run(['build', '--content', content, '--output', output]);
      expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<h1>Post</h1>');
      expect(stdout).toHaveBeenCalledWith('Generated 1 page.\n');
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });

  it('rejects unsupported commands and incomplete options', async () => {
    await expect(run(['serve'])).rejects.toThrow('Usage: ssg build');
    await expect(run(['build', '--content'])).rejects.toThrow('--content requires a directory');
  });
});
