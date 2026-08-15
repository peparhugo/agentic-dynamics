import fs from 'fs';
import path from 'path';
import os from 'os';
import http from 'http';
import { serve } from './serve';

describe('serve', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');

    fs.mkdirSync(contentDir, { recursive: true });
    fs.mkdirSync(outputDir, { recursive: true });

    const content = `---
title: Test Page
---
# Hello

This is a test page.`;

    fs.writeFileSync(path.join(contentDir, 'test.md'), content);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('serves files from the output directory', async () => {
    const testPort = 9000 + Math.floor(Math.random() * 1000);

    const html = `<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<h1>Test Page</h1>
</body>
</html>`;

    fs.writeFileSync(path.join(outputDir, 'test.html'), html);
    fs.writeFileSync(path.join(outputDir, 'index.html'), '<html><body>Index</body></html>');

    const server = await serve({
      contentDir,
      outputDir,
      port: testPort
    }, true);

    try {
      const response = await new Promise<string>((resolve, reject) => {
        http.get(`http://localhost:${testPort}/test.html`, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => resolve(data));
        }).on('error', reject);
      });

      expect(response).toContain('<h1>Test Page</h1>');
      expect(response).toContain('__live-reload__');
    } finally {
      await server.close();
    }
  });

  it('injects live reload script into HTML files', async () => {
    const testPort = 9000 + Math.floor(Math.random() * 1000);

    const html = `<!DOCTYPE html>
<html>
<body>
<h1>Test</h1>
</body>
</html>`;

    fs.writeFileSync(path.join(outputDir, 'index.html'), html);

    const server = await serve({
      contentDir,
      outputDir,
      port: testPort
    }, true);

    try {
      const response = await new Promise<string>((resolve, reject) => {
        http.get(`http://localhost:${testPort}/`, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => resolve(data));
        }).on('error', reject);
      });

      expect(response).toContain('__live-reload__');
      expect(response).toContain('WebSocket');
      expect(response).toContain('window.location.reload');
    } finally {
      await server.close();
    }
  });

  it('returns 404 for non-existent files', async () => {
    const testPort = 9000 + Math.floor(Math.random() * 1000);

    fs.writeFileSync(path.join(outputDir, 'index.html'), '<html><body>Index</body></html>');

    const server = await serve({
      contentDir,
      outputDir,
      port: testPort
    }, true);

    try {
      await new Promise<void>((resolve, reject) => {
        http.get(`http://localhost:${testPort}/non-existent.html`, (res) => {
          if (res.statusCode === 404) {
            resolve();
          } else {
            reject(new Error(`Expected 404, got ${res.statusCode}`));
          }
        }).on('error', reject);
      });
    } finally {
      await server.close();
    }
  });

  it('serves index.html for directory requests', async () => {
    const testPort = 9000 + Math.floor(Math.random() * 1000);

    fs.writeFileSync(path.join(outputDir, 'index.html'), '<html><body>Index Page</body></html>');

    const server = await serve({
      contentDir,
      outputDir,
      port: testPort
    }, true);

    try {
      const response = await new Promise<string>((resolve, reject) => {
        http.get(`http://localhost:${testPort}/`, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => resolve(data));
        }).on('error', reject);
      });

      expect(response).toContain('Index Page');
    } finally {
      await server.close();
    }
  });
});
