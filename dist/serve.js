"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.serve = serve;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const chokidar_1 = __importDefault(require("chokidar"));
const ssg_1 = require("./ssg");
const LIVE_RELOAD_SCRIPT = `<script>(function(){var w=new WebSocket('ws://'+location.host);w.onmessage=function(e){if(e.data==='reload')location.reload()}})();</script>`;
const MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
};
function injectLiveReload(html) {
    if (html.includes('</body>')) {
        return html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
    }
    return html + LIVE_RELOAD_SCRIPT;
}
function serve(options) {
    const { contentDir, outputDir, templateDir, port } = options;
    (0, ssg_1.build)({ contentDir, outputDir, templateDir });
    const server = http_1.default.createServer((req, res) => {
        const url = req.url === '/' ? '/index.html' : req.url || '/';
        const filePath = path_1.default.join(outputDir, url);
        if (fs_1.default.existsSync(filePath) && fs_1.default.statSync(filePath).isFile()) {
            const ext = path_1.default.extname(filePath);
            const contentType = MIME_TYPES[ext] || 'application/octet-stream';
            let content = fs_1.default.readFileSync(filePath, 'utf-8');
            if (ext === '.html') {
                content = injectLiveReload(content);
            }
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content);
        }
        else {
            res.writeHead(404);
            res.end('Not found');
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
    const watchDirs = [];
    if (fs_1.default.existsSync(contentDir)) {
        watchDirs.push(contentDir);
    }
    if (templateDir && fs_1.default.existsSync(templateDir)) {
        watchDirs.push(templateDir);
    }
    const watcher = chokidar_1.default.watch(watchDirs, {
        ignoreInitial: true,
        awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
    });
    function rebuild() {
        try {
            (0, ssg_1.build)({ contentDir, outputDir, templateDir });
            notifyClients();
        }
        catch (err) {
            // nop
        }
    }
    watcher.on('change', rebuild);
    watcher.on('add', rebuild);
    watcher.on('unlink', rebuild);
    server.listen(port, () => {
        console.log(`Dev server running at http://localhost:${port}`);
    });
    return { server, watcher, wss };
}
//# sourceMappingURL=serve.js.map