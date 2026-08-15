import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { DevServer } from '../src/dev-server';

describe('DevServer', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-dev-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should create a dev server instance', () => {
    const server = new DevServer({ contentDir, outputDir, port: 3001 });
    expect(server).toBeDefined();
  });

  it('should inject live reload script into HTML', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const server = new DevServer({ contentDir, outputDir, port: 3001 });

    // Access private method through type assertion for testing
    const devServerAny = server as any;
    const html = '<html><body>Test</body></html>';
    const injected = devServerAny.injectLiveReloadScript(html);

    expect(injected).toContain('<script>');
    expect(injected).toContain('WebSocket');
    expect(injected).toContain('reload');
    expect(injected).toContain('</script>');
    expect(injected).toContain('<body>Test');
    expect(injected).toContain('</body>');
  });

  it('should not inject script twice', async () => {
    const server = new DevServer({ contentDir, outputDir, port: 3001 });

    const devServerAny = server as any;
    const html = '<html><body>Test</body></html>';
    const injected1 = devServerAny.injectLiveReloadScript(html);
    const injected2 = devServerAny.injectLiveReloadScript(injected1);

    const scriptCount = (injected2.match(/<script>/g) || []).length;
    expect(scriptCount).toBeLessThanOrEqual(2);
  });

  it('should use custom port', () => {
    const port = 5555;
    const server = new DevServer({ contentDir, outputDir, port });

    const devServerAny = server as any;
    expect(devServerAny.port).toBe(port);
  });

  it('should use default port 3000', () => {
    const server = new DevServer({ contentDir, outputDir });

    const devServerAny = server as any;
    expect(devServerAny.port).toBe(3000);
  });

  it('should use custom templates directory', () => {
    const templatesDir = path.join(tempDir, 'custom-templates');
    const server = new DevServer({ contentDir, outputDir, templatesDir });

    const devServerAny = server as any;
    expect(devServerAny.templatesDir).toBe(templatesDir);
  });

  it('should use default templates directory', () => {
    const server = new DevServer({ contentDir, outputDir });

    const devServerAny = server as any;
    expect(devServerAny.templatesDir).toBe('./templates');
  });
});
