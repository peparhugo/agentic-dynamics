import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
export class CacheManager {
    constructor(outputDir) {
        this.cacheFile = path.join(outputDir, '.ssg-cache.json');
        this.manifest = this.loadManifest();
    }
    loadManifest() {
        if (fs.existsSync(this.cacheFile)) {
            try {
                const content = fs.readFileSync(this.cacheFile, 'utf-8');
                return JSON.parse(content);
            }
            catch {
                return { version: '1.0.0', entries: {} };
            }
        }
        return { version: '1.0.0', entries: {} };
    }
    hashContent(content) {
        return crypto.createHash('sha256').update(content).digest('hex');
    }
    saveManifest() {
        const outputDir = path.dirname(this.cacheFile);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        fs.writeFileSync(this.cacheFile, JSON.stringify(this.manifest, null, 2));
    }
    getEntry(filename) {
        return this.manifest.entries[filename];
    }
    setEntry(filename, entry) {
        this.manifest.entries[filename] = entry;
    }
    hasEntry(filename) {
        return filename in this.manifest.entries;
    }
    removeEntry(filename) {
        delete this.manifest.entries[filename];
    }
    isFileChanged(filename, fileContent, templatePath, layoutPath) {
        const entry = this.getEntry(filename);
        if (!entry) {
            return true;
        }
        const fileHash = this.hashContent(fileContent);
        if (fileHash !== entry.fileHash) {
            return true;
        }
        if (templatePath && fs.existsSync(templatePath)) {
            const templateContent = fs.readFileSync(templatePath, 'utf-8');
            const templateHash = this.hashContent(templateContent);
            if (templateHash !== entry.templateHash) {
                return true;
            }
        }
        if (layoutPath && fs.existsSync(layoutPath)) {
            const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
            const layoutHash = this.hashContent(layoutContent);
            if (layoutHash !== entry.layoutHash) {
                return true;
            }
        }
        return false;
    }
    updateEntry(filename, fileContent, html, templatePath, layoutPath, metadata) {
        const fileHash = this.hashContent(fileContent);
        let templateHash;
        let layoutHash;
        if (templatePath && fs.existsSync(templatePath)) {
            const templateContent = fs.readFileSync(templatePath, 'utf-8');
            templateHash = this.hashContent(templateContent);
        }
        if (layoutPath && fs.existsSync(layoutPath)) {
            const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
            layoutHash = this.hashContent(layoutContent);
        }
        this.setEntry(filename, {
            filename,
            fileHash,
            templateHash,
            layoutHash,
            html,
            title: metadata?.title,
            date: metadata?.date,
            tags: metadata?.tags,
            timestamp: Date.now(),
        });
    }
    clear() {
        this.manifest.entries = {};
    }
    getEntries() {
        return Object.values(this.manifest.entries);
    }
    getAllFilenames() {
        return Object.keys(this.manifest.entries);
    }
}
//# sourceMappingURL=cache-manager.js.map