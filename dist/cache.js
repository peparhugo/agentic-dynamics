import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
export class CacheManager {
    constructor(outputDir) {
        this.buildStartTime = Date.now();
        this.cachePath = path.join(outputDir, '.ssg-cache.json');
        this.cacheData = this.loadCache();
    }
    loadCache() {
        if (fs.existsSync(this.cachePath)) {
            try {
                const data = fs.readFileSync(this.cachePath, 'utf-8');
                return JSON.parse(data);
            }
            catch (error) {
                return { version: 1, entries: {} };
            }
        }
        return { version: 1, entries: {} };
    }
    computeHash(content) {
        return crypto
            .createHash('sha256')
            .update(content)
            .digest('hex');
    }
    getFileHash(filePath) {
        if (!fs.existsSync(filePath)) {
            return '';
        }
        const content = fs.readFileSync(filePath, 'utf-8');
        return this.computeHash(content);
    }
    hasChanged(fileKey, content, templatePath) {
        const currentHash = this.computeHash(content);
        const templateHash = templatePath ? this.getFileHash(templatePath) : undefined;
        const cached = this.cacheData.entries[fileKey];
        if (!cached) {
            return true;
        }
        if (cached.hash !== currentHash) {
            return true;
        }
        if (templateHash && cached.templateHash !== templateHash) {
            return true;
        }
        return false;
    }
    updateEntry(fileKey, content, templatePath) {
        const hash = this.computeHash(content);
        const templateHash = templatePath ? this.getFileHash(templatePath) : undefined;
        this.cacheData.entries[fileKey] = {
            hash,
            templateHash,
            timestamp: Date.now()
        };
    }
    save() {
        const dir = path.dirname(this.cachePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(this.cachePath, JSON.stringify(this.cacheData, null, 2), 'utf-8');
    }
    clear() {
        this.cacheData = { version: 1, entries: {} };
    }
    getStats(pagesBuilt, pagesSkipped) {
        const timeSaved = pagesSkipped > 0 ? Date.now() - this.buildStartTime : 0;
        return {
            pagesBuilt,
            pagesSkipped,
            timeSaved
        };
    }
}
//# sourceMappingURL=cache.js.map