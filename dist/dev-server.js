"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.injectLiveReloadScript = injectLiveReloadScript;
exports.startDevServer = startDevServer;
const http_1 = __importDefault(require("http"));
const path_1 = __importDefault(require("path"));
const fs_1 = require("fs");
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const index_1 = require("./index");
const MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
};
function getMimeType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    return MIME_TYPES[ext] || "application/octet-stream";
}
function injectLiveReloadScript(html, port) {
    const script = `<script>(function(){var ws=new WebSocket("ws://localhost:${port}/__livereload");ws.onmessage=function(m){if(m.data==="reload"){window.location.reload();}};})();</script>`;
    return html.replace("</body>", script + "</body>");
}
async function serveFile(filePath, res, port) {
    try {
        await fs_1.promises.access(filePath);
        const stat = await fs_1.promises.stat(filePath);
        if (stat.isDirectory()) {
            const indexPath = path_1.default.join(filePath, "index.html");
            try {
                await fs_1.promises.access(indexPath);
                filePath = indexPath;
            }
            catch {
                res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
                res.end();
                return;
            }
        }
        let content = await fs_1.promises.readFile(filePath);
        const ext = path_1.default.extname(filePath).toLowerCase();
        if (ext === ".html") {
            let html = content.toString("utf-8");
            html = injectLiveReloadScript(html, port);
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end(html, "utf-8");
        }
        else {
            res.writeHead(200, { "Content-Type": getMimeType(filePath) });
            res.end(content);
        }
    }
    catch {
        res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("Not Found");
    }
}
async function startDevServer(options) {
    const contentDir = path_1.default.resolve(options.contentDir);
    const outputDir = path_1.default.resolve(options.outputDir);
    const templatesDir = options.templatesDir
        ? path_1.default.resolve(options.templatesDir)
        : path_1.default.resolve("templates");
    const port = options.port;
    await (0, index_1.build)({
        contentDir,
        outputDir,
        templatesDir,
    });
    const server = http_1.default.createServer((req, res) => {
        if (!req.url) {
            res.writeHead(404);
            res.end();
            return;
        }
        const urlPath = req.url === "/" ? "/index.html" : req.url.split("?")[0];
        const filePath = path_1.default.join(outputDir, urlPath);
        serveFile(filePath, res, port);
    });
    const wss = new ws_1.WebSocketServer({ server, path: "/__livereload" });
    let rebuildTimer = null;
    const clients = new Set();
    wss.on("connection", (ws) => {
        clients.add(ws);
        ws.on("close", () => {
            clients.delete(ws);
        });
    });
    async function doRebuild() {
        try {
            await (0, index_1.build)({
                contentDir,
                outputDir,
                templatesDir,
            });
            for (const client of clients) {
                if (client.readyState === ws_1.WebSocket.OPEN) {
                    client.send("reload");
                }
            }
        }
        catch (err) {
            console.error("Rebuild error:", err.message);
        }
    }
    const watcher = chokidar_1.default.watch([contentDir, templatesDir], {
        ignoreInitial: true,
    });
    watcher.on("all", () => {
        if (rebuildTimer) {
            clearTimeout(rebuildTimer);
        }
        rebuildTimer = setTimeout(() => {
            rebuildTimer = null;
            doRebuild();
        }, 100);
    });
    return new Promise((resolve) => {
        server.listen(port, () => {
            console.log(`Dev server running at http://localhost:${port}/`);
            resolve({
                server,
                wss,
                close: async () => {
                    await watcher.close();
                    if (rebuildTimer) {
                        clearTimeout(rebuildTimer);
                    }
                    wss.close();
                    await new Promise((r) => server.close(() => r()));
                },
            });
        });
    });
}
