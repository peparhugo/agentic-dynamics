import { parseMarkdown } from '../parser.js';
export class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
        this.version = '1.0.0';
    }
    async onFile(context, file) {
        if (!file.filename.endsWith('.md')) {
            return;
        }
        const parsed = await parseMarkdown(file.content);
        file.parsed = parsed;
    }
}
//# sourceMappingURL=markdown-plugin.js.map