"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
jest.mock('chokidar');
const http = __importStar(require("http"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const os = __importStar(require("os"));
const serve_1 = require("../src/serve");
function tmpDir() {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}
function writeMarkdown(dir, slug, content, frontmatter = '') {
    const fm = frontmatter ? `${frontmatter}\n` : '';
    fs.writeFileSync(path.join(dir, `${slug}.md`), `---\n${fm}---\n${content}`);
}
function fetch(url, port) {
    return new Promise((resolve, reject) => {
        const req = http.get(`http://localhost:${port}${url}`, (res) => {
            let body = '';
            res.on('data', (chunk) => { body += chunk; });
            res.on('end', () => resolve({ status: res.statusCode || 0, body }));
        });
        req.on('error', reject);
    });
}
describe('injectReloadScript', () => {
    it('injects script before </body> tag', () => {
        const html = '<html><head></head><body><p>Hello</p></body></html>';
        const result = (0, serve_1.injectReloadScript)(html);
        expect(result).toContain('<script>');
        expect(result).toContain('new WebSocket');
        expect(result).toContain('location.reload');
        expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
        expect(result).toContain('<p>Hello</p>');
        expect(result).toContain('</body>');
        expect(result).toContain('</html>');
    });
    it('injects script before </html> when no </body> tag', () => {
        const html = '<html><head></head><p>Hello</p></html>';
        const result = (0, serve_1.injectReloadScript)(html);
        expect(result).toContain('<script>');
        expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</html>'));
    });
    it('appends script at end when no closing tags found', () => {
        const html = '<html><head></head><body>';
        const result = (0, serve_1.injectReloadScript)(html);
        expect(result).toContain('<script>');
        expect(result.endsWith('</script>')).toBe(true);
    });
});
describe('ssg serve', () => {
    let contentDir;
    let outputDir;
    let server;
    let port;
    beforeEach(() => {
        contentDir = tmpDir();
        outputDir = tmpDir();
        port = 3000 + Math.floor(Math.random() * 1000);
    });
    afterEach((done) => {
        fs.rmSync(contentDir, { recursive: true, force: true });
        fs.rmSync(outputDir, { recursive: true, force: true });
        if (server) {
            server.close(() => done());
        }
        else {
            done();
        }
    });
    it('starts a server on the given port', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', () => {
            fetch('/', port).then((res) => {
                expect(res.status).toBe(200);
                done();
            }).catch(done);
        });
    });
    it('serves HTML files from the output directory', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', async () => {
            try {
                const res = await fetch('/hello.html', port);
                expect(res.status).toBe(200);
                expect(res.body).toContain('Hello');
                done();
            }
            catch (err) {
                done(err);
            }
        });
    });
    it('serves index.html at the root path', (done) => {
        writeMarkdown(contentDir, 'post', 'Content', 'title: My Post');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', async () => {
            try {
                const res = await fetch('/', port);
                expect(res.status).toBe(200);
                expect(res.body).toContain('My Post');
                done();
            }
            catch (err) {
                done(err);
            }
        });
    });
    it('returns 404 for non-existent files', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', async () => {
            try {
                const res = await fetch('/nonexistent.html', port);
                expect(res.status).toBe(404);
                done();
            }
            catch (err) {
                done(err);
            }
        });
    });
    it('injects reload script into served HTML pages', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', async () => {
            try {
                const res = await fetch('/hello.html', port);
                expect(res.status).toBe(200);
                expect(res.body).toContain('new WebSocket');
                expect(res.body).toContain('location.reload');
                done();
            }
            catch (err) {
                done(err);
            }
        });
    });
    it('injects reload script into index page', (done) => {
        writeMarkdown(contentDir, 'post', 'Content', 'title: Post');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', async () => {
            try {
                const res = await fetch('/', port);
                expect(res.status).toBe(200);
                expect(res.body).toContain('new WebSocket');
                done();
            }
            catch (err) {
                done(err);
            }
        });
    });
    it('uses default port 3000 when no port is specified', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir });
        server.on('listening', () => {
            const addr = server.address();
            expect(addr).not.toBeNull();
            if (addr && typeof addr === 'object') {
                expect(addr.port).toBe(3000);
            }
            done();
        });
    });
    it('builds the site on startup', (done) => {
        writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
        server = (0, serve_1.serve)({ content: contentDir, output: outputDir, port });
        server.on('listening', () => {
            expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
            expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
            done();
        });
    });
});
//# sourceMappingURL=serve.test.js.map