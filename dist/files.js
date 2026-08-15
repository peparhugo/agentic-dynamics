"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.readMarkdownFiles = readMarkdownFiles;
exports.writeFile = writeFile;
exports.ensureDir = ensureDir;
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
async function readMarkdownFiles(contentDir) {
    const files = [];
    try {
        const entries = await fs_1.promises.readdir(contentDir);
        for (const entry of entries) {
            if (entry.endsWith('.md')) {
                const filePath = path_1.default.join(contentDir, entry);
                const content = await fs_1.promises.readFile(filePath, 'utf-8');
                files.push({
                    name: entry,
                    path: filePath,
                    content
                });
            }
        }
    }
    catch (error) {
        if (error.code === 'ENOENT') {
            await fs_1.promises.mkdir(contentDir, { recursive: true });
        }
        else {
            throw error;
        }
    }
    return files;
}
async function writeFile(filePath, content) {
    const dir = path_1.default.dirname(filePath);
    await fs_1.promises.mkdir(dir, { recursive: true });
    await fs_1.promises.writeFile(filePath, content, 'utf-8');
}
async function ensureDir(dirPath) {
    await fs_1.promises.mkdir(dirPath, { recursive: true });
}
//# sourceMappingURL=files.js.map