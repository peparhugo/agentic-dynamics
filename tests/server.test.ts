import { startServer } from '../src/server';
import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import net from 'net';

function get(
  port: number,
  urlPath: string
): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${urlPath}`, (res) => {
      let body = '';
      res.on('data', (chunk: Buffer) => (body += chunk.toString()));
      res.on('end', () =>
        resolve({ status: res.statusCode || 0, body })
      );
    }).on('error', reject);
  });
}

function rawGet(
  port: number,
  rawPath: string
): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const socket = new net.Socket();
    socket.connect(port, 'localhost', () => {
      socket.write(
        `GET ${rawPath} HTTP/1.1\r\nHost: localhost:${port}\r\nConnection: close\r\n\r\n`
      );
    });
    let data = '';
    socket.on('data', (chunk: Buffer) => {
      data += chunk.toString();
    });
    socket.on('end', () => {
      const statusMatch = data.match(/HTTP\/1\.1 (\d+)/);
      const status = statusMatch ? parseInt(statusMatch[1], 10) : 0;
      const bodyStart = data.indexOf('\r\n\r\n');
      const body = bodyStart >= 0 ? data.slice(bodyStart + 4) : '';
      resolve({ status, body });
    });
    socket.on('error', reject);
  });
}

async function waitForServer(port: number, retries = 30): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      await get(port, '/');
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  throw new Error('Server did not start');
}

describe('startServer', () => {
  let outputDir: string;
  let contentDir: string;
  let templateDir: string;
  let port: number;
  let serverInstance: {
    server: http.Server;
    close: () => Promise<void>;
    rebuild: () => void;
  };

  beforeEach(async () => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
    templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.mkdirSync(path.join(templateDir, 'partials'));

    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body><nav>{{> nav}}</nav>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article><h1>{{title}}</h1>{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>All Posts</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'partials', 'nav.hbs'),
      '<a href="index.html">Home</a>'
    );

    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello World
date: 2024-01-15
tags:
  - intro
---
# Hello World
Welcome to my site.`
    );

    const { generateSite } = require('../src/generator');
    const { parseDirectory } = require('../src/parser');

    const pages = parseDirectory(contentDir);
    generateSite(pages, outputDir, templateDir);

    const result = startServer({
      port: 0,
      content: contentDir,
      output: outputDir,
      templates: templateDir,
    });
    serverInstance = result as unknown as typeof serverInstance;
    port = (serverInstance.server.address() as { port: number }).port;

    await waitForServer(port);
  });

  afterEach(async () => {
    await serverInstance.close();
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templateDir, { recursive: true, force: true });
  });

  it('serves index.html at /', async () => {
    const { status, body } = await get(port, '/');
    expect(status).toBe(200);
    expect(body).toContain('All Posts');
    expect(body).toContain('Hello World');
    expect(body).toContain('hello.html');
  });

  it('serves page files by slug', async () => {
    const { status, body } = await get(port, '/hello.html');
    expect(status).toBe(200);
    expect(body).toContain('Hello World');
    expect(body).toContain('Welcome to my site.');
  });

  it('returns 404 for non-existent files', async () => {
    const { status, body } = await get(port, '/nonexistent.html');
    expect(status).toBe(404);
    expect(body).toContain('Not Found');
  });

  it('injects live-reload WebSocket script into HTML responses', async () => {
    const { body } = await get(port, '/hello.html');
    expect(body).toContain("new WebSocket('ws://' + location.host)");
    expect(body).toContain('location.reload()');
  });

  it('injects live-reload script into index page', async () => {
    const { body } = await get(port, '/');
    expect(body).toContain("new WebSocket('ws://' + location.host)");
    expect(body).toContain('location.reload()');
  });

  it('does not modify non-HTML responses', async () => {
    const cssPath = path.join(outputDir, 'test.css');
    fs.writeFileSync(cssPath, 'body { color: red; }');

    const { body } = await get(port, '/test.css');
    expect(body).toBe('body { color: red; }');
    expect(body).not.toContain('WebSocket');

    fs.unlinkSync(cssPath);
  });

  it('prevents path traversal via raw HTTP request', async () => {
    const { status } = await rawGet(port, '/../../../etc/passwd');
    expect(status).toBe(403);
  });

  it('rebuilds site when rebuild is triggered', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'new-post.md'),
      `---
title: New Post
date: 2024-06-01
tags: []
---
# New Post
This is new content.`
    );

    serverInstance.rebuild();

    await new Promise((r) => setTimeout(r, 200));

    const { body: indexBody } = await get(port, '/');
    expect(indexBody).toContain('New Post');
    expect(indexBody).toContain('new-post.html');

    const { body: pageBody } = await get(port, '/new-post.html');
    expect(pageBody).toContain('New Post');
    expect(pageBody).toContain('This is new content.');
  });

  it('rebuilds site when template changes', async () => {
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Updated Posts</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
    );

    serverInstance.rebuild();

    await new Promise((r) => setTimeout(r, 200));

    const { body } = await get(port, '/');
    expect(body).toContain('Updated Posts');
    expect(body).not.toContain('All Posts');
  });

  it('serves index.html for / path', async () => {
    const { status, body } = await get(port, '/index.html');
    expect(status).toBe(200);
    expect(body).toContain('All Posts');
  });
});
