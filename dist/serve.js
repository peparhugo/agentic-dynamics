"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.LIVE_RELOAD_PATH = void 0;
exports.injectLiveReloadScript = injectLiveReloadScript;
exports.startServer = startServer;
const fs_1 = __importDefault(require("fs"));
const http_1 = __importDefault(require("http"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const site_1 = require("./site");
exports.LIVE_RELOAD_PATH = '/__ssg_livereload';
function liveReloadScript() {
    return `<script data-ssg-livereload>
(function () {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var ws = new WebSocket(protocol + '//' + location.host + '${exports.LIVE_RELOAD_PATH}');
  ws.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  });
})();
</script>`;
}
function injectLiveReloadScript(html) {
    const script = liveReloadScript();
    if (html.includes('</body>')) {
        return html.replace('</body>', `${script}\n</body>`);
    }
    if (html.includes('</html>')) {
        return html.replace('</html>', `${script}\n</html>`);
    }
    return html + script;
}
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.mjs': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.map': 'application/json; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.eot': 'application/vnd.ms-fontobject',
    '.xml': 'application/xml; charset=utf-8',
};
async function startServer(options = {}) {
    const contentDir = path_1.default.resolve(options.content ?? './content');
    const outputDir = path_1.default.resolve(options.output ?? './dist');
    const templatesDir = path_1.default.resolve(options.templates ?? './templates');
    const host = options.host ?? 'localhost';
    const requestedPort = options.port ?? 3000;
    const rebuild = () => {
        try {
            (0, site_1.buildSite)({ contentDir, outputDir, templatesDir });
        }
        catch (err) {
            console.error('Rebuild failed:', err);
        }
    };
    const server = http_1.default.createServer((req, res) => {
        const raw = req.url ?? '/';
        const queryIndex = raw.indexOf('?');
        const rawPath = queryIndex === -1 ? raw : raw.slice(0, queryIndex);
        let pathname = decodeURIComponent(rawPath);
        if (pathname === '/') {
            pathname = '/index.html';
        }
        const relative = pathname.replace(/^\/+/, '');
        const filePath = path_1.default.resolve(outputDir, relative);
        if (filePath !== outputDir && !filePath.startsWith(outputDir + path_1.default.sep)) {
            res.statusCode = 403;
            res.setHeader('Content-Type', 'text/plain; charset=utf-8');
            res.end('Forbidden');
            return;
        }
        fs_1.default.readFile(filePath, (err, data) => {
            if (err) {
                res.statusCode = 404;
                res.setHeader('Content-Type', 'text/plain; charset=utf-8');
                res.end('Not Found');
                return;
            }
            const ext = path_1.default.extname(filePath).toLowerCase();
            res.setHeader('Content-Type', MIME_TYPES[ext] ?? 'application/octet-stream');
            if (ext === '.html') {
                data = Buffer.from(injectLiveReloadScript(data.toString('utf-8')));
            }
            res.end(data);
        });
    });
    const wss = new ws_1.WebSocketServer({ server, path: exports.LIVE_RELOAD_PATH });
    let closed = false;
    let rebuildTimer = null;
    const broadcastReload = () => {
        for (const client of wss.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        }
    };
    const scheduleRebuild = () => {
        if (rebuildTimer) {
            clearTimeout(rebuildTimer);
        }
        rebuildTimer = setTimeout(() => {
            rebuildTimer = null;
            rebuild();
            broadcastReload();
        }, 150);
    };
    const watcher = chokidar_1.default.watch([contentDir, templatesDir], {
        ignoreInitial: true,
        ignored: (watchedPath) => {
            const resolved = path_1.default.resolve(watchedPath);
            return resolved === outputDir || resolved.startsWith(outputDir + path_1.default.sep);
        },
    });
    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);
    watcher.on('addDir', scheduleRebuild);
    watcher.on('unlinkDir', scheduleRebuild);
    rebuild();
    await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(requestedPort, host, () => {
            resolve();
        });
    });
    const address = server.address();
    const close = () => {
        return new Promise((resolve) => {
            if (closed) {
                resolve();
                return;
            }
            closed = true;
            if (rebuildTimer) {
                clearTimeout(rebuildTimer);
                rebuildTimer = null;
            }
            for (const client of wss.clients) {
                client.terminate();
            }
            watcher.close().then(() => {
                wss.close(() => {
                    server.close(() => resolve());
                });
            });
        });
    };
    return {
        server,
        wss,
        watcher,
        port: address.port,
        host,
        address: `http://${host}:${address.port}`,
        outputDir,
        close,
        rebuild,
    };
}
