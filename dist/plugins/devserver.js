"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = void 0;
exports.createDevServer = createDevServer;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const chokidar_1 = __importDefault(require("chokidar"));
const build_1 = require("../build");
function getMimeType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    const mimeTypes = {
        '.html': 'text/html',
        '.htm': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    };
    return mimeTypes[ext] || 'application/octet-stream';
}
function injectReloadScript(html, port) {
    const script = `<script>(function(){var s=new WebSocket('ws://localhost:${port}/__livereload');s.onmessage=function(m){if(m.data==='reload')window.location.reload()};})();</script>`;
    if (html.includes('</body>')) {
        return html.replace('</body>', script + '</body>');
    }
    return html + script;
}
exports.DevServerPlugin = {
    name: 'dev-server',
};
function createDevServer(options) {
    const { contentDir, outputDir, templatesDir, port } = options;
    const resolvedOutputDir = path_1.default.resolve(outputDir);
    const resolvedTemplatesDir = path_1.default.resolve(templatesDir || './templates');
    (0, build_1.build)({ contentDir, outputDir, templatesDir });
    const server = http_1.default.createServer((req, res) => {
        const url = req.url || '/';
        const reqPath = url === '/' ? 'index.html' : url;
        const relativePath = reqPath.startsWith('/') ? reqPath.slice(1) : reqPath;
        const filePath = path_1.default.join(resolvedOutputDir, relativePath);
        const resolved = path_1.default.resolve(filePath);
        if (!resolved.startsWith(resolvedOutputDir + path_1.default.sep) && resolved !== resolvedOutputDir) {
            res.writeHead(403);
            res.end('Forbidden');
            return;
        }
        if (!fs_1.default.existsSync(resolved) || !fs_1.default.statSync(resolved).isFile()) {
            res.writeHead(404);
            res.end('Not Found');
            return;
        }
        const mimeType = getMimeType(resolved);
        if (mimeType === 'text/html') {
            let html = fs_1.default.readFileSync(resolved, 'utf-8');
            html = injectReloadScript(html, port);
            res.writeHead(200, { 'Content-Type': mimeType });
            res.end(html);
        }
        else {
            const content = fs_1.default.readFileSync(resolved);
            res.writeHead(200, { 'Content-Type': mimeType });
            res.end(content);
        }
    });
    const wss = new ws_1.WebSocketServer({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
        const { pathname } = new URL(request.url || '', `http://localhost:${port}`);
        if (pathname === '/__livereload') {
            wss.handleUpgrade(request, socket, head, (ws) => {
                wss.emit('connection', ws, request);
            });
        }
        else {
            socket.destroy();
        }
    });
    const clients = new Set();
    wss.on('connection', (ws) => {
        clients.add(ws);
        ws.on('close', () => {
            clients.delete(ws);
        });
    });
    const watchPaths = [
        path_1.default.resolve(contentDir),
        resolvedTemplatesDir,
    ];
    let rebuildTimeout = null;
    const watcher = chokidar_1.default.watch(watchPaths, {
        ignoreInitial: true,
        awaitWriteFinish: {
            stabilityThreshold: 200,
            pollInterval: 100,
        },
    });
    watcher.on('all', (event, filePath) => {
        console.log(`[change] ${event}: ${filePath}`);
        if (rebuildTimeout)
            clearTimeout(rebuildTimeout);
        rebuildTimeout = setTimeout(() => {
            try {
                (0, build_1.build)({ contentDir, outputDir, templatesDir });
                console.log('[rebuilt]');
                for (const client of clients) {
                    if (client.readyState === ws_1.WebSocket.OPEN) {
                        client.send('reload');
                    }
                }
            }
            catch (err) {
                console.error('[build error]', err.message);
            }
        }, 150);
    });
    server.on('close', () => {
        watcher.close();
        wss.close();
    });
    server.listen(port, () => {
        console.log(`Dev server running at http://localhost:${port}/`);
    });
    return server;
}
//# sourceMappingURL=devserver.js.map