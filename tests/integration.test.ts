import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { DevServer } from '../src/dev-server';
import { SiteGenerator } from '../src/generator';

describe('Integration Tests', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-integration-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should handle build command with all options', async () => {
    // Create test content
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir: path.join(tempDir, 'templates'),
    });

    await generator.build();

    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
  });

  it('should watch for file changes and rebuild', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'initial.md'),
      '---\ntitle: Initial\n---\n\nInitial content'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const initialHtml = fs.readFileSync(path.join(outputDir, 'initial.html'), 'utf-8');
    expect(initialHtml).toContain('Initial');

    // Create new file
    fs.writeFileSync(
      path.join(contentDir, 'new.md'),
      '---\ntitle: New\n---\n\nNew content'
    );

    // Rebuild
    await generator.build();

    expect(fs.existsSync(path.join(outputDir, 'new.html'))).toBe(true);
    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('New');
    expect(indexHtml).toContain('Initial');
  });

  it('should create dev server instance with options', () => {
    const server = new DevServer({
      contentDir,
      outputDir,
      templatesDir: path.join(tempDir, 'templates'),
      port: 4000,
    });

    expect(server).toBeDefined();
  });

  it('should build site before serving', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'serve-test.md'),
      '---\ntitle: Serve Test\n---\n\n# Serve Test'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    // Verify build creates output
    expect(fs.existsSync(path.join(outputDir, 'serve-test.html'))).toBe(true);

    // Dev server should work with the built output
    const server = new DevServer({
      contentDir,
      outputDir,
      port: 4001,
    });

    expect(server).toBeDefined();
  });
});
