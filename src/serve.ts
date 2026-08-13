import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar from 'chokidar';
import WebSocket from 'ws';
import { parseMarkdown } from './parser';
import { generatePageHTML, generateIndexHTML } from './generator';
import { TemplateEngine } from './template-engine';

interface ServeOptions {
  content: string;
  output: string;
  templates?: string;
  port: number;
}

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  const port = parseInt(window.location.port) + 1;
  const ws = new WebSocket('ws://localhost:' + port);
  ws.addEventListener('message', (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
  ws.addEventListener('close', () => {
    setTimeout(() => window.location.reload(), 1000);
  });
})();
</script>
`;

async function build(options: ServeOptions): Promise<void> {
  const { content: contentDir, output: outputDir, templates: templatesDir } = options;

  if (!fs.existsSync(contentDir)) {
    console.error(`Error: Content directory "${contentDir}" does not exist`);
    return;
  }

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  let templateEngine: TemplateEngine | undefined;
  if (templatesDir && fs.existsSync(templatesDir)) {
    templateEngine = new TemplateEngine({ templateDir: templatesDir });
  }

  const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));

  if (files.length === 0) {
    console.warn(`Warning: No markdown files found in "${contentDir}"`);
  }

  const pages = [];

  for (const file of files) {
    const filePath = path.join(contentDir, file);
    const content = fs.readFileSync(filePath, 'utf-8');
    const slug = path.parse(file).name;

    try {
      const page = await parseMarkdown(content, slug);
      pages.push(page);

      const outputFile = path.join(outputDir, `${slug}.html`);
      const html = generatePageHTML(page, templateEngine);
      fs.writeFileSync(outputFile, html, 'utf-8');
      console.log(`✓ Rebuilt ${outputFile}`);
    } catch (error) {
      console.error(`Error processing ${file}:`, error);
    }
  }

  const indexFile = path.join(outputDir, 'index.html');
  const indexHtml = generateIndexHTML(pages);
  fs.writeFileSync(indexFile, indexHtml, 'utf-8');
  console.log(`✓ Rebuilt ${indexFile}`);
}

function injectLiveReloadScript(html: string): string {
  return html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
}

export async function serve(options: ServeOptions): Promise<void> {
  console.log(`Starting dev server on http://localhost:${options.port}`);
  console.log(`WebSocket server on ws://localhost:${options.port + 1}`);

  const server = http.createServer((req, res) => {
    const filePath = path.join(options.output, req.url === '/' ? 'index.html' : req.url);
    const normalizedPath = path.normalize(filePath);

    if (!normalizedPath.startsWith(path.normalize(options.output))) {
      res.writeHead(403, { 'Content-Type': 'text/plain' });
      res.end('Forbidden');
      return;
    }

    if (fs.existsSync(normalizedPath) && fs.statSync(normalizedPath).isFile()) {
      const content = fs.readFileSync(normalizedPath, 'utf-8');
      const contentType = normalizedPath.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      let responseContent = content;

      if (normalizedPath.endsWith('.html')) {
        responseContent = injectLiveReloadScript(content);
      }

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(responseContent);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  });

  const wss = new WebSocket.Server({ port: options.port + 1 });

  let isBuilding = false;

  async function rebuild(): Promise<void> {
    if (isBuilding) return;
    isBuilding = true;
    console.log('Detected changes, rebuilding...');

    try {
      await build(options);
      console.log('Build complete!');
      wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
          client.send('reload');
        }
      });
    } catch (error) {
      console.error('Build error:', error);
    } finally {
      isBuilding = false;
    }
  }

  const watcher = chokidar.watch([options.content, ...(options.templates ? [options.templates] : [])], {
    ignored: /(^|[/\\])\./,
    persistent: true,
  });

  watcher.on('change', () => rebuild());
  watcher.on('add', () => rebuild());
  watcher.on('unlink', () => rebuild());

  server.listen(options.port, 'localhost', () => {
    console.log(`Dev server listening on http://localhost:${options.port}`);
    build(options).catch(error => console.error('Initial build failed:', error));
  });

  wss.on('close', () => {
    watcher.close();
  });
}
