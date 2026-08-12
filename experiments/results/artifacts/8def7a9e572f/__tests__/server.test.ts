import http from 'http';
import fs from 'fs';
import path from 'path';
import {
  createServer,
  injectLiveReload,
  LIVE_RELOAD_SCRIPT,
} from '../src/server';

const tmpDir = path.join(__dirname, '..', '.test-tmp-server');

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

function createDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

function makeRequest(url: string): Promise<{ statusCode: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (chunk: Buffer) => chunks.push(chunk));
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode || 0,
          body: Buffer.concat(chunks).toString('utf-8'),
        });
      });
    }).on('error', reject);
  });
}

describe('injectLiveReload', () => {
  it('injects script before closing body tag', () => {
    const result = injectLiveReload('<html><body><h1>Test</h1></body></html>');
    expect(result).toContain(LIVE_RELOAD_SCRIPT);
    expect(result.endsWith('</body></html>')).toBe(true);
    expect(result).toBe(
      `<html><body><h1>Test</h1>${LIVE_RELOAD_SCRIPT}</body></html>`
    );
  });

  it('appends script when no closing body tag', () => {
    const result = injectLiveReload('<html><p>No body</p></html>');
    expect(result).toContain(LIVE_RELOAD_SCRIPT);
    expect(result).toBe(`<html><p>No body</p></html>${LIVE_RELOAD_SCRIPT}`);
  });

  it('injects before first body tag when multiple', () => {
    const result = injectLiveReload('<body>First</body><body>Second</body>');
    expect(result).toContain(LIVE_RELOAD_SCRIPT);
    expect(result).toBe(
      `<body>First${LIVE_RELOAD_SCRIPT}</body><body>Second</body>`
    );
  });
});

describe('dev server', () => {
  let server: http.Server;
  let port: number;
  let outputDir: string;
  let contentDir: string;

  beforeEach((done) => {
    contentDir = createDir('serve-content');
    outputDir = createDir('serve-output');

    writeFile(
      outputDir,
      'index.html',
      '<!DOCTYPE html><html><head></head><body><h1>Test</h1></body></html>'
    );
    writeFile(
      outputDir,
      'style.css',
      'body { color: red; }'
    );

    const srv = createServer({
      content: contentDir,
      output: outputDir,
      port: 0,
    });

    srv.listen(0, () => {
      const addr = srv.address();
      if (addr && typeof addr === 'object') {
        port = addr.port;
      }
      server = srv;
      done();
    });
  });

  afterEach((done) => {
    if (server) {
      server.close(() => done());
    } else {
      done();
    }
  });

  it('serves HTML with live reload script injected', async () => {
    const { statusCode, body } = await makeRequest(
      `http://localhost:${port}/index.html`
    );
    expect(statusCode).toBe(200);
    expect(body).toContain('<h1>Test</h1>');
    expect(body).toContain(LIVE_RELOAD_SCRIPT);
  });

  it('serves non-HTML files without injection', async () => {
    const { statusCode, body } = await makeRequest(
      `http://localhost:${port}/style.css`
    );
    expect(statusCode).toBe(200);
    expect(body).toContain('color: red');
    expect(body).not.toContain(LIVE_RELOAD_SCRIPT);
  });

  it('returns 404 for non-existent files', async () => {
    const { statusCode } = await makeRequest(
      `http://localhost:${port}/nonexistent.html`
    );
    expect(statusCode).toBe(404);
  });

  it('serves index.html for root path', async () => {
    const { statusCode, body } = await makeRequest(
      `http://localhost:${port}/`
    );
    expect(statusCode).toBe(200);
    expect(body).toContain('<h1>Test</h1>');
    expect(body).toContain(LIVE_RELOAD_SCRIPT);
  });
});
