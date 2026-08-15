"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseFrontmatter = parseFrontmatter;
function parseFrontmatter(content) {
    const lines = content.split('\n');
    if (!lines[0].startsWith('---')) {
        return { data: {}, content };
    }
    let endIndex = -1;
    for (let i = 1; i < lines.length; i++) {
        if (lines[i].startsWith('---')) {
            endIndex = i;
            break;
        }
    }
    if (endIndex === -1) {
        return { data: {}, content };
    }
    const frontmatterBlock = lines.slice(1, endIndex).join('\n');
    const markdownContent = lines.slice(endIndex + 1).join('\n');
    const data = parseYAML(frontmatterBlock);
    return { data, content: markdownContent };
}
function parseYAML(yamlStr) {
    const data = {};
    if (!yamlStr.trim()) {
        return data;
    }
    const lines = yamlStr.split('\n');
    for (const line of lines) {
        if (!line.trim() || line.trim().startsWith('#')) {
            continue;
        }
        const colonIndex = line.indexOf(':');
        if (colonIndex === -1) {
            continue;
        }
        const key = line.substring(0, colonIndex).trim();
        let value = line.substring(colonIndex + 1).trim();
        if (value.startsWith('"') && value.endsWith('"')) {
            value = value.slice(1, -1);
        }
        else if (value.startsWith("'") && value.endsWith("'")) {
            value = value.slice(1, -1);
        }
        else if (value === 'true') {
            data[key] = true;
            continue;
        }
        else if (value === 'false') {
            data[key] = false;
            continue;
        }
        else if (value.startsWith('[') && value.endsWith(']')) {
            const arrayStr = value.slice(1, -1);
            data[key] = arrayStr.split(',').map(item => item.trim());
            continue;
        }
        data[key] = value;
    }
    return data;
}
//# sourceMappingURL=frontmatter.js.map