"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = exports.LIVE_RELOAD_SCRIPT = void 0;
exports.injectLiveReload = injectLiveReload;
exports.createServer = createServer;
exports.startServer = startServer;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const generator_1 = require("../generator");
exports.LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function (msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>`;
function injectLiveReload(html) {
    if (html.includes('</body>')) {
        return html.replace('</body>', `${exports.LIVE_RELOAD_SCRIPT}</body>`);
    }
    return html + exports.LIVE_RELOAD_SCRIPT;
}
const mimeTypes = {
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
function createServer(options) {
    const { content, output, templates } = options;
    const server = http_1.default.createServer((req, res) => {
        const urlPath = req.url === '/' ? '/index.html' : req.url || '/';
        const filePath = path_1.default.join(output, urlPath);
        const resolved = path_1.default.resolve(filePath);
        if (!resolved.startsWith(path_1.default.resolve(output))) {
            res.writeHead(403);
            res.end('Forbidden');
            return;
        }
        if (!fs_1.default.existsSync(filePath) || fs_1.default.statSync(filePath).isDirectory()) {
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Not Found');
            return;
        }
        const ext = path_1.default.extname(filePath).toLowerCase();
        const contentType = mimeTypes[ext] || 'application/octet-stream';
        try {
            if (ext === '.html') {
                let content = fs_1.default.readFileSync(filePath, 'utf-8');
                content = injectLiveReload(content);
                res.writeHead(200, { 'Content-Type': contentType });
                res.end(content);
            }
            else {
                const content = fs_1.default.readFileSync(filePath);
                res.writeHead(200, { 'Content-Type': contentType });
                res.end(content);
            }
        }
        catch {
            res.writeHead(500);
            res.end('Internal Server Error');
        }
    });
    const wss = new ws_1.WebSocketServer({ server });
    const clients = new Set();
    wss.on('connection', (ws) => {
        clients.add(ws);
        ws.on('close', () => clients.delete(ws));
    });
    function notifyClients() {
        for (const client of clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        }
    }
    const watchDirs = [content];
    if (templates && fs_1.default.existsSync(templates)) {
        watchDirs.push(templates);
    }
    const watcher = chokidar_1.default.watch(watchDirs, { ignoreInitial: true });
    let buildTimeout = null;
    watcher.on('all', () => {
        if (buildTimeout)
            clearTimeout(buildTimeout);
        buildTimeout = setTimeout(() => {
            (0, generator_1.generateSite)(content, output, templates);
            notifyClients();
        }, 100);
    });
    server.on('close', () => {
        watcher.close();
        wss.close();
    });
    return server;
}
function startServer(options) {
    (0, generator_1.generateSite)(options.content, options.output, options.templates);
    const server = createServer(options);
    server.listen(options.port, () => {
        console.log(`Dev server running at http://localhost:${options.port}`);
    });
    return server;
}
class DevServerPlugin {
    constructor() {
        this.name = 'devserver';
    }
    onStart() { }
    afterBuild() { }
    onEnd() { }
}
exports.DevServerPlugin = DevServerPlugin;
//# sourceMappingURL=devserver.js.map