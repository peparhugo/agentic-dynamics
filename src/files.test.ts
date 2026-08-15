import { promises as fs } from 'fs';
import path from 'path';
import { readMarkdownFiles, writeFile, ensureDir } from './files';

const testDir = path.join(__dirname, '..', '__test_temp__');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

describe('files', () => {
  beforeEach(async () => {
    await cleanup();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('readMarkdownFiles', () => {
    it('should read markdown files from directory', async () => {
      const contentDir = path.join(testDir, 'content');
      await fs.mkdir(contentDir, { recursive: true });

      await fs.writeFile(path.join(contentDir, 'post1.md'), '# Post 1');
      await fs.writeFile(path.join(contentDir, 'post2.md'), '# Post 2');
      await fs.writeFile(path.join(contentDir, 'other.txt'), 'Not markdown');

      const files = await readMarkdownFiles(contentDir);

      expect(files).toHaveLength(2);
      expect(files.map(f => f.name).sort()).toEqual(['post1.md', 'post2.md']);
      expect(files[0].content).toBeDefined();
    });

    it('should create directory if it does not exist', async () => {
      const contentDir = path.join(testDir, 'nonexistent');

      const files = await readMarkdownFiles(contentDir);

      expect(files).toHaveLength(0);

      const exists = await fs.stat(contentDir).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should handle empty directory', async () => {
      const contentDir = path.join(testDir, 'empty');
      await fs.mkdir(contentDir, { recursive: true });

      const files = await readMarkdownFiles(contentDir);

      expect(files).toHaveLength(0);
    });

    it('should ignore non-markdown files', async () => {
      const contentDir = path.join(testDir, 'content');
      await fs.mkdir(contentDir, { recursive: true });

      await fs.writeFile(path.join(contentDir, 'post.md'), '# Post');
      await fs.writeFile(path.join(contentDir, 'image.png'), 'fake image');
      await fs.writeFile(path.join(contentDir, 'doc.txt'), 'text file');

      const files = await readMarkdownFiles(contentDir);

      expect(files).toHaveLength(1);
      expect(files[0].name).toBe('post.md');
    });
  });

  describe('writeFile', () => {
    it('should write file to disk', async () => {
      const filePath = path.join(testDir, 'output', 'test.html');
      const content = '<html>test</html>';

      await writeFile(filePath, content);

      const written = await fs.readFile(filePath, 'utf-8');
      expect(written).toBe(content);
    });

    it('should create directories if they do not exist', async () => {
      const filePath = path.join(testDir, 'deep', 'nested', 'path', 'file.html');

      await writeFile(filePath, '<html>test</html>');

      const exists = await fs.stat(filePath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should overwrite existing files', async () => {
      const filePath = path.join(testDir, 'file.txt');
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, 'old content');

      await writeFile(filePath, 'new content');

      const content = await fs.readFile(filePath, 'utf-8');
      expect(content).toBe('new content');
    });
  });

  describe('ensureDir', () => {
    it('should create directory', async () => {
      const dirPath = path.join(testDir, 'mydir');

      await ensureDir(dirPath);

      const exists = await fs.stat(dirPath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should handle existing directory', async () => {
      const dirPath = path.join(testDir, 'existing');
      await fs.mkdir(dirPath, { recursive: true });

      await ensureDir(dirPath);

      const exists = await fs.stat(dirPath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should create nested directories', async () => {
      const dirPath = path.join(testDir, 'nested', 'deep', 'path');

      await ensureDir(dirPath);

      const exists = await fs.stat(dirPath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });
  });
});
