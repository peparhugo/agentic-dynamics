"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.serve = serve;
const express_1 = __importDefault(require("express"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const http_1 = require("http");
const chokidar_1 = __importDefault(require("chokidar"));
const fs_1 = require("fs");
const files_1 = require("./files");
const page_1 = require("./page");
const generator_1 = require("./generator");
let clients = [];
function broadcastReload() {
    const message = JSON.stringify({ type: 'reload' });
    clients = clients.filter(client => client.readyState === ws_1.WebSocket.OPEN);
    clients.forEach(client => {
        client.send(message);
    });
}
function injectReloadScript(html) {
    const script = `<script>
(function() {
  const ws = new WebSocket('ws://' + window.location.host);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'reload') {
      window.location.reload();
    }
  };
  ws.onerror = () => {
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  };
})();
</script>`;
    if (html.includes('</body>')) {
        return html.replace('</body>', script + '\n</body>');
    }
    return html + script;
}
async function serveFile(filePath, distDir) {
    try {
        let content = await fs_1.promises.readFile(filePath, 'utf-8');
        if (filePath.endsWith('.html')) {
            content = injectReloadScript(content);
        }
        return content;
    }
    catch (error) {
        throw error;
    }
}
async function rebuild(contentDir, distDir, templateDir) {
    try {
        console.log('Rebuilding...');
        const files = await (0, files_1.readMarkdownFiles)(contentDir);
        if (files.length === 0) {
            console.log('No markdown files found.');
            return;
        }
        const pages = [];
        for (const file of files) {
            const page = await (0, page_1.processMarkdownFile)(file.name, file.content);
            pages.push(page);
            await (0, generator_1.generatePageHtml)(page, distDir, templateDir);
        }
        await (0, generator_1.generateIndexHtml)(pages, distDir);
        console.log('Build complete, reloading browser...');
        broadcastReload();
    }
    catch (error) {
        console.error('Rebuild error:', error.message);
    }
}
async function serve(distDir, contentDir, templateDir, port = 3000) {
    const app = (0, express_1.default)();
    const server = (0, http_1.createServer)(app);
    const wss = new ws_1.WebSocketServer({ server });
    wss.on('connection', (ws) => {
        clients.push(ws);
    });
    app.use(express_1.default.static(distDir));
    app.get('*', async (req, res) => {
        let requestPath = req.path === '/' ? '/index.html' : req.path;
        if (!requestPath.endsWith('.html')) {
            requestPath += '.html';
        }
        const filePath = path_1.default.join(distDir, requestPath);
        try {
            const content = await serveFile(filePath, distDir);
            res.type('text/html').send(content);
        }
        catch (error) {
            res.status(404).type('text/html').send(injectReloadScript(`<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body><h1>404 - Page not found</h1></body>
</html>`));
        }
    });
    server.listen(port, () => {
        console.log(`Dev server running at http://localhost:${port}`);
    });
    const watchDirs = [contentDir];
    if (templateDir) {
        watchDirs.push(templateDir);
    }
    const watcher = chokidar_1.default.watch(watchDirs, {
        ignored: /node_modules/,
        persistent: true
    });
    let rebuildTimeout;
    watcher.on('change', () => {
        clearTimeout(rebuildTimeout);
        rebuildTimeout = setTimeout(() => {
            rebuild(contentDir, distDir, templateDir);
        }, 300);
    });
    return new Promise(() => {
        process.on('SIGINT', () => {
            console.log('\nServer stopped');
            watcher.close();
            server.close();
            process.exit(0);
        });
    });
}
//# sourceMappingURL=serve.js.map