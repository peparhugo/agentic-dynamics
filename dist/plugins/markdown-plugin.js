import fs from 'fs';
import path from 'path';
import { parseMarkdownWithYaml } from '../parser.js';
function slugFromFilename(filename) {
    return filename.replace(/\.md$/, '');
}
export class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
        this.beforeBuild = this.beforeBuild.bind(this);
    }
    async beforeBuild(context) {
        const { contentDir, pages } = context;
        if (!fs.existsSync(contentDir)) {
            throw new Error(`Content directory not found: ${contentDir}`);
        }
        const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));
        if (files.length === 0) {
            throw new Error(`No markdown files found in ${contentDir}`);
        }
        for (const file of files) {
            const filePath = path.join(contentDir, file);
            const content = fs.readFileSync(filePath, 'utf-8');
            const parsed = await parseMarkdownWithYaml(content);
            const page = {
                slug: slugFromFilename(file),
                filename: file,
                content: parsed.content,
                metadata: parsed.metadata
            };
            pages.push(page);
        }
    }
}
//# sourceMappingURL=markdown-plugin.js.map