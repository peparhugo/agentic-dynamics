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
const generator_1 = require("./generator");
const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(protocol + '//' + location.host);
  socket.addEventListener('message', function(event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
  socket.addEventListener('close', function() {
    setTimeout(function() { location.reload(); }, 2000);
  });
})();
</script>`;
function injectLiveReload(html) {
    if (html.includes('</body>')) {
        return html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
    }
    return html + LIVE_RELOAD_SCRIPT;
}
const CONTENT_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
};
function startDevServer(options) {
    const { content, output, templates, port } = options;
    try {
        (0, generator_1.buildSite)(content, output, templates);
        console.log(`Initial build complete`);
    }
    catch (err) {
        console.log(`Initial build skipped: ${err.message}`);
    }
    const server = http_1.default.createServer((req, res) => {
        const reqUrl = req.url || '/';
        if (reqUrl === '/ws' || reqUrl.startsWith('/ws?')) {
            res.writeHead(200, { 'Content-Type': 'text/plain' });
            res.end('WebSocket endpoint');
            return;
        }
        const url = new URL(reqUrl, `http://localhost`);
        let filePath = path_1.default.join(output, url.pathname === '/' ? '/index.html' : url.pathname);
        if (!path_1.default.extname(filePath)) {
            filePath = path_1.default.join(filePath, 'index.html');
        }
        const ext = path_1.default.extname(filePath).toLowerCase();
        const contentType = CONTENT_TYPES[ext] || 'application/octet-stream';
        try {
            const fileContent = fs_1.default.readFileSync(filePath);
            if (ext === '.html') {
                const html = injectLiveReload(fileContent.toString('utf-8'));
                res.writeHead(200, { 'Content-Type': 'text/html' });
                res.end(html);
                return;
            }
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(fileContent);
        }
        catch {
            const origExt = path_1.default.extname(reqUrl || '').toLowerCase();
            if (!origExt) {
                try {
                    const indexPath = path_1.default.join(output, 'index.html');
                    const html = injectLiveReload(fs_1.default.readFileSync(indexPath, 'utf-8'));
                    res.writeHead(200, { 'Content-Type': 'text/html' });
                    res.end(html);
                    return;
                }
                catch {
                    // fall through to 404
                }
            }
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Not Found');
        }
    });
    const wss = new ws_1.WebSocketServer({ server });
    const clients = new Set();
    wss.on('connection', (ws) => {
        clients.add(ws);
        ws.on('close', () => clients.delete(ws));
    });
    const watchPaths = [];
    if (fs_1.default.existsSync(content))
        watchPaths.push(content);
    if (fs_1.default.existsSync(templates))
        watchPaths.push(templates);
    const watcher = chokidar_1.default.watch(watchPaths, {
        ignoreInitial: true,
    });
    let rebuildTimeout = null;
    function triggerRebuild() {
        if (rebuildTimeout)
            clearTimeout(rebuildTimeout);
        rebuildTimeout = setTimeout(() => {
            try {
                console.log('Rebuilding...');
                (0, generator_1.buildSite)(content, output, templates);
                console.log('Rebuild complete');
                for (const client of clients) {
                    if (client.readyState === ws_1.WebSocket.OPEN) {
                        client.send('reload');
                    }
                }
            }
            catch (err) {
                console.error('Rebuild error:', err.message);
            }
        }, 200);
    }
    watcher.on('change', triggerRebuild);
    watcher.on('add', triggerRebuild);
    watcher.on('unlink', triggerRebuild);
    return new Promise((resolve, reject) => {
        let chokidarReady = watchPaths.length === 0;
        watcher.on('ready', () => {
            chokidarReady = true;
        });
        server.listen(port, () => {
            const actualPort = server.address().port;
            console.log(`Dev server running at http://localhost:${actualPort}`);
            function resolveWhenReady() {
                if (chokidarReady) {
                    resolve({
                        port: actualPort,
                        close: async () => {
                            if (rebuildTimeout)
                                clearTimeout(rebuildTimeout);
                            await watcher.close();
                            for (const client of clients) {
                                client.terminate();
                            }
                            wss.close();
                            await new Promise((resolveClose) => {
                                server.close(() => resolveClose());
                            });
                        },
                    });
                }
                else {
                    setTimeout(resolveWhenReady, 10);
                }
            }
            resolveWhenReady();
        });
        server.on('error', reject);
    });
}
//# sourceMappingURL=server.js.map