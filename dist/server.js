"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.startDevServer = startDevServer;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const chokidar_1 = __importDefault(require("chokidar"));
const parser_1 = require("./parser");
const generator_1 = require("./generator");
const RELOAD_SCRIPT = `<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      ws.close();
      location.reload();
    }
  };
  ws.onclose = function() {
    console.log('[ssg] Live-reload disconnected. Attempting reconnect in 1s...');
    setTimeout(function() {
      location.reload();
    }, 1000);
  };
})();
</script>`;
function build(options) {
    const parseResult = (0, parser_1.parseFiles)({ contentDir: options.contentDir, outputDir: options.outputDir });
    (0, generator_1.generateSite)(parseResult, options.outputDir, options.templatesDir);
    console.log(`[ssg] Site rebuilt`);
}
function injectReloadScript(html) {
    if (html.includes('</body>')) {
        return html.replace('</body>', RELOAD_SCRIPT + '\n</body>');
    }
    return html + RELOAD_SCRIPT;
}
function getContentType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    const types = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    };
    return types[ext] || 'application/octet-stream';
}
function serveFile(res, filePath, injectWs) {
    try {
        const content = fs_1.default.readFileSync(filePath);
        const contentType = getContentType(filePath);
        if (injectWs && contentType.startsWith('text/html')) {
            const html = injectReloadScript(content.toString('utf-8'));
            res.writeHead(200, {
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Length': Buffer.byteLength(html),
            });
            res.end(html);
            return;
        }
        res.writeHead(200, {
            'Content-Type': contentType,
            'Content-Length': content.length,
        });
        res.end(content);
    }
    catch {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
    }
}
function startDevServer(options) {
    const clients = new Set();
    build(options);
    const server = http_1.default.createServer((req, res) => {
        const url = req.url || '/';
        const filePath = url === '/' || url.endsWith('/')
            ? path_1.default.join(options.outputDir, 'index.html')
            : path_1.default.join(options.outputDir, url);
        if (fs_1.default.existsSync(filePath) && fs_1.default.statSync(filePath).isFile()) {
            serveFile(res, filePath, true);
        }
        else {
            const indexPath = path_1.default.join(options.outputDir, 'index.html');
            if (fs_1.default.existsSync(indexPath)) {
                serveFile(res, indexPath, true);
            }
            else {
                res.writeHead(404, { 'Content-Type': 'text/plain' });
                res.end('Not Found');
            }
        }
    });
    const wss = new ws_1.WebSocketServer({ server });
    wss.on('connection', (ws) => {
        clients.add(ws);
        ws.on('close', () => {
            clients.delete(ws);
        });
    });
    function notifyClients() {
        const msg = 'reload';
        for (const client of clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send(msg);
            }
        }
    }
    let rebuildTimer = null;
    function scheduleRebuild() {
        if (rebuildTimer)
            clearTimeout(rebuildTimer);
        rebuildTimer = setTimeout(() => {
            try {
                build(options);
                notifyClients();
            }
            catch (err) {
                const message = err instanceof Error ? err.message : String(err);
                console.error(`[ssg] Build error: ${message}`);
            }
        }, 150);
    }
    const watcher = chokidar_1.default.watch([
        options.contentDir,
        options.templatesDir,
    ], {
        ignoreInitial: true,
        persistent: true,
        usePolling: true,
        interval: 100,
    });
    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);
    server.on('close', () => {
        watcher.close();
        wss.close();
    });
    server.listen(options.port, () => {
        console.log(`[ssg] Dev server running at http://localhost:${options.port}`);
        console.log(`[ssg] Watching ${options.contentDir}/ and ${options.templatesDir}/ for changes`);
    });
    return server;
}
