"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createServer = createServer;
exports.serve = serve;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const chokidar_1 = __importDefault(require("chokidar"));
const parser_1 = require("./parser");
const generator_1 = require("./generator");
function rebuild(content, output, templates) {
    const pages = (0, parser_1.parseMarkdownFiles)(content);
    (0, generator_1.generateSite)(pages, output, templates);
    return pages.length;
}
function getMimeType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    const mimes = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
    };
    return mimes[ext] || 'application/octet-stream';
}
function injectLiveReload(html, port) {
    const script = `<script>
(function() {
  var ws = new WebSocket('ws://localhost:${port}');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
})();
</script>`;
    return html.replace('</body>', script + '\n</body>');
}
function createServer(options) {
    const { content, output, templates, port } = options;
    const resolvedOutput = path_1.default.resolve(output);
    rebuild(content, output, templates);
    const server = http_1.default.createServer((req, res) => {
        const url = req.url || '/';
        const sanitized = path_1.default.normalize(url).replace(/^(\.\.[/\\])+/, '');
        const relativePath = sanitized.replace(/^[/\\]+/, '');
        const filePath = relativePath
            ? path_1.default.join(resolvedOutput, relativePath)
            : path_1.default.join(resolvedOutput, 'index.html');
        try {
            if (!fs_1.default.existsSync(filePath) || !fs_1.default.statSync(filePath).isFile()) {
                res.writeHead(404);
                res.end('Not found');
                return;
            }
            const ext = path_1.default.extname(filePath).toLowerCase();
            const content = fs_1.default.readFileSync(filePath);
            if (ext === '.html') {
                const addr = server.address();
                const actualPort = typeof addr === 'object' && addr ? addr.port : port;
                const html = injectLiveReload(content.toString('utf-8'), actualPort);
                res.writeHead(200, { 'Content-Type': 'text/html' });
                res.end(html);
            }
            else {
                res.writeHead(200, { 'Content-Type': getMimeType(filePath) });
                res.end(content);
            }
        }
        catch {
            res.writeHead(500);
            res.end('Internal server error');
        }
    });
    const wss = new ws_1.WebSocketServer({ server });
    const resolvedContent = path_1.default.resolve(content);
    const resolvedTemplates = path_1.default.resolve(templates);
    const watcher = chokidar_1.default.watch([resolvedContent, resolvedTemplates], {
        ignoreInitial: true,
    });
    watcher.on('all', () => {
        rebuild(content, output, templates);
        wss.clients.forEach((client) => {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        });
    });
    server._watcher = watcher;
    server._wss = wss;
    return server;
}
function serve(options) {
    const server = createServer(options);
    server.listen(options.port, () => {
        console.log(`Dev server running at http://localhost:${options.port}`);
    });
    return server;
}
//# sourceMappingURL=server.js.map