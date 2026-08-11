"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = void 0;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      var ws2 = new WebSocket('ws://' + location.host);
      ws2.onmessage = function(msg) {
        if (msg.data === 'reload') location.reload();
      };
      ws2.onclose = function() {
        setTimeout(function() {
          location.reload();
        }, 1000);
      };
    }, 1000);
  };
})();
</script>
</body>`;
function injectReloadScript(html) {
    if (html.includes('</body>')) {
        return html.replace('</body>', RELOAD_SCRIPT);
    }
    return html + RELOAD_SCRIPT.replace('</body>', '');
}
function getContentType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    const types = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    };
    return types[ext] || 'application/octet-stream';
}
function serveFile(res, filePath) {
    try {
        const content = fs_1.default.readFileSync(filePath);
        const contentType = getContentType(filePath);
        let body = content;
        if (contentType === 'text/html') {
            let html = content.toString('utf-8');
            html = injectReloadScript(html);
            body = Buffer.from(html, 'utf-8');
        }
        res.writeHead(200, {
            'Content-Type': contentType,
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Content-Length': String(body.length),
        });
        res.end(body);
    }
    catch {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
    }
}
class DevServerPlugin {
    constructor() {
        this.name = 'devserver';
        this.wss = null;
        this.clients = new Set();
        this.watcher = null;
        this.rebuildTimer = null;
        this.server = null;
        this.rebuildCallback = null;
    }
    onEnd(_context) {
        this.cleanup();
    }
    async startServer(context, rebuildFn) {
        this.rebuildCallback = rebuildFn;
        const { port, content, output, templates } = context.options;
        this.wss = new ws_1.WebSocketServer({ noServer: true });
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            ws.on('close', () => this.clients.delete(ws));
        });
        this.watcher = chokidar_1.default.watch([content, templates], {
            ignoreInitial: true,
            usePolling: true,
            interval: 100,
        });
        this.watcher.on('all', () => {
            if (this.rebuildTimer)
                clearTimeout(this.rebuildTimer);
            this.rebuildTimer = setTimeout(() => this.rebuild(), 150);
        });
        this.server = http_1.default.createServer((req, res) => {
            if (!req.url) {
                res.writeHead(404);
                res.end('Not Found');
                return;
            }
            let urlPath = req.url.split('?')[0];
            if (urlPath === '/') {
                urlPath = '/index.html';
            }
            const resolvedOutput = path_1.default.resolve(output);
            const relativePath = urlPath.replace(/^\//, '');
            const resolvedPath = path_1.default.resolve(output, relativePath);
            if (!resolvedPath.startsWith(resolvedOutput + path_1.default.sep) && resolvedPath !== resolvedOutput) {
                res.writeHead(403, { 'Content-Type': 'text/plain' });
                res.end('Forbidden');
                return;
            }
            serveFile(res, resolvedPath);
        });
        this.server.on('upgrade', (req, socket, head) => {
            if (this.wss) {
                this.wss.handleUpgrade(req, socket, head, (ws) => {
                    this.wss.emit('connection', ws, req);
                });
            }
        });
        await new Promise((resolve) => {
            this.server.listen(port, () => {
                console.log(`Dev server running at http://localhost:${this.server.address().port}`);
                console.log(`Watching ${content}/ and ${templates}/ for changes`);
                resolve();
            });
        });
        const close = async () => {
            this.cleanup();
        };
        return {
            server: this.server,
            close,
            rebuild: () => this.rebuild(),
        };
    }
    async rebuild() {
        try {
            if (this.rebuildCallback) {
                await this.rebuildCallback();
            }
            this.broadcastReload();
        }
        catch (err) {
            console.error('Build error:', err);
        }
    }
    broadcastReload() {
        for (const client of this.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        }
    }
    cleanup() {
        if (this.watcher) {
            this.watcher.close();
            this.watcher = null;
        }
        for (const client of this.clients) {
            client.close();
        }
        this.clients.clear();
        if (this.wss) {
            this.wss.close();
            this.wss = null;
        }
        if (this.server) {
            this.server.close();
            this.server = null;
        }
    }
}
exports.DevServerPlugin = DevServerPlugin;
//# sourceMappingURL=devserver.js.map