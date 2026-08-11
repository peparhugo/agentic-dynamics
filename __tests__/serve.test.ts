jest.mock('chokidar');

import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { injectReloadScript, serve, ServeOptions } from '../src/serve';

function tmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function writeMarkdown(dir: string, slug: string, content: string, frontmatter: string = '') {
  const fm = frontmatter ? `${frontmatter}\n` : '';
  fs.writeFileSync(path.join(dir, `${slug}.md`), `---\n${fm}---\n${content}`);
}

function fetch(url: string, port: number): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://localhost:${port}${url}`, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => resolve({ status: res.statusCode || 0, body }));
    });
    req.on('error', reject);
  });
}

describe('injectReloadScript', () => {
  it('injects script before </body> tag', () => {
    const html = '<html><head></head><body><p>Hello</p></body></html>';
    const result = injectReloadScript(html);
    expect(result).toContain('<script>');
    expect(result).toContain('new WebSocket');
    expect(result).toContain('location.reload');
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
    expect(result).toContain('<p>Hello</p>');
    expect(result).toContain('</body>');
    expect(result).toContain('</html>');
  });

  it('injects script before </html> when no </body> tag', () => {
    const html = '<html><head></head><p>Hello</p></html>';
    const result = injectReloadScript(html);
    expect(result).toContain('<script>');
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</html>'));
  });

  it('appends script at end when no closing tags found', () => {
    const html = '<html><head></head><body>';
    const result = injectReloadScript(html);
    expect(result).toContain('<script>');
    expect(result.endsWith('</script>')).toBe(true);
  });
});

describe('ssg serve', () => {
  let contentDir: string;
  let outputDir: string;
  let server: http.Server;
  let port: number;

  beforeEach(() => {
    contentDir = tmpDir();
    outputDir = tmpDir();
    port = 3000 + Math.floor(Math.random() * 1000);
  });

  afterEach((done) => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    if (server) {
      server.close(() => done());
    } else {
      done();
    }
  });

  it('starts a server on the given port', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', () => {
      fetch('/', port).then((res) => {
        expect(res.status).toBe(200);
        done();
      }).catch(done);
    });
  });

  it('serves HTML files from the output directory', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', async () => {
      try {
        const res = await fetch('/hello.html', port);
        expect(res.status).toBe(200);
        expect(res.body).toContain('Hello');
        done();
      } catch (err) {
        done(err);
      }
    });
  });

  it('serves index.html at the root path', (done) => {
    writeMarkdown(contentDir, 'post', 'Content', 'title: My Post');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', async () => {
      try {
        const res = await fetch('/', port);
        expect(res.status).toBe(200);
        expect(res.body).toContain('My Post');
        done();
      } catch (err) {
        done(err);
      }
    });
  });

  it('returns 404 for non-existent files', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', async () => {
      try {
        const res = await fetch('/nonexistent.html', port);
        expect(res.status).toBe(404);
        done();
      } catch (err) {
        done(err);
      }
    });
  });

  it('injects reload script into served HTML pages', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', async () => {
      try {
        const res = await fetch('/hello.html', port);
        expect(res.status).toBe(200);
        expect(res.body).toContain('new WebSocket');
        expect(res.body).toContain('location.reload');
        done();
      } catch (err) {
        done(err);
      }
    });
  });

  it('injects reload script into index page', (done) => {
    writeMarkdown(contentDir, 'post', 'Content', 'title: Post');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', async () => {
      try {
        const res = await fetch('/', port);
        expect(res.status).toBe(200);
        expect(res.body).toContain('new WebSocket');
        done();
      } catch (err) {
        done(err);
      }
    });
  });

  it('uses default port 3000 when no port is specified', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir });

    server.on('listening', () => {
      const addr = server.address();
      expect(addr).not.toBeNull();
      if (addr && typeof addr === 'object') {
        expect(addr.port).toBe(3000);
      }
      done();
    });
  });

  it('builds the site on startup', (done) => {
    writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
    server = serve({ content: contentDir, output: outputDir, port });

    server.on('listening', () => {
      expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
      expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
      done();
    });
  });
});
