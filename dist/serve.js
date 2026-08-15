"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.liveReloadScript = liveReloadScript;
exports.injectLiveReload = injectLiveReload;
exports.serve = serve;
const http_1 = require("http");
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const build_1 = require("./build");
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
};
function liveReloadScript() {
    return [
        '<script data-ssg-live-reload>',
        '(function(){',
        '  var ws=new WebSocket("ws://"+location.host);',
        '  ws.onmessage=function(e){ if(e.data==="reload"){ location.reload(); } };',
        '})();',
        '</script>',
    ].join('\n');
}
function injectLiveReload(html) {
    const script = liveReloadScript();
    if (/<\/body>/i.test(html)) {
        return html.replace(/<\/body>/i, `${script}\n</body>`);
    }
    return `${html}\n${script}\n`;
}
async function serve(options) {
    const contentDir = path_1.default.resolve(options.content);
    const outputDir = path_1.default.resolve(options.output);
    const templatesDir = options.templates ?? './templates';
    const requestedPort = options.port ?? 3000;
    const server = (0, http_1.createServer)((req, res) => {
        void handleRequest(req, res, outputDir);
    });
    const wss = new ws_1.WebSocketServer({ server });
    let building = false;
    let queued = false;
    function broadcastReload() {
        for (const client of wss.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        }
    }
    async function rebuild() {
        if (building) {
            queued = true;
            return;
        }
        building = true;
        try {
            await (0, build_1.build)({ content: contentDir, output: outputDir, templates: templatesDir });
            broadcastReload();
        }
        finally {
            building = false;
            if (queued) {
                queued = false;
                await rebuild();
            }
        }
    }
    const watcher = chokidar_1.default.watch([contentDir, templatesDir], {
        ignoreInitial: true,
    });
    let debounceTimer = null;
    const scheduleRebuild = () => {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(() => {
            debounceTimer = null;
            void rebuild();
        }, 50);
    };
    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);
    watcher.on('addDir', scheduleRebuild);
    watcher.on('unlinkDir', scheduleRebuild);
    await rebuild();
    await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(requestedPort, () => {
            server.removeListener('error', reject);
            resolve();
        });
    });
    const address = server.address();
    const port = address.port;
    return {
        port,
        reload: broadcastReload,
        async close() {
            if (debounceTimer) {
                clearTimeout(debounceTimer);
                debounceTimer = null;
            }
            await watcher.close();
            for (const client of wss.clients) {
                client.terminate();
            }
            await new Promise((resolve) => {
                wss.close(() => resolve());
            });
            await new Promise((resolve, reject) => {
                server.close((err) => (err ? reject(err) : resolve()));
            });
        },
    };
}
async function handleRequest(req, res, outputDir) {
    const rawUrl = (req.url ?? '/').split('?')[0];
    const urlPath = decodeURIComponent(rawUrl);
    let filePath;
    if (urlPath === '/' || urlPath === '') {
        filePath = path_1.default.join(outputDir, 'index.html');
    }
    else {
        filePath = path_1.default.resolve(outputDir, urlPath.slice(1));
    }
    const relative = path_1.default.relative(outputDir, filePath);
    if (relative.startsWith('..') || path_1.default.isAbsolute(relative)) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Forbidden');
        return;
    }
    try {
        const stat = await fs_1.promises.stat(filePath);
        if (stat.isDirectory()) {
            filePath = path_1.default.join(filePath, 'index.html');
        }
    }
    catch {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
    }
    let content;
    try {
        content = await fs_1.promises.readFile(filePath);
    }
    catch {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
    }
    const ext = path_1.default.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';
    if (ext === '.html') {
        content = Buffer.from(injectLiveReload(content.toString('utf8')), 'utf8');
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
}
//# sourceMappingURL=serve.js.map