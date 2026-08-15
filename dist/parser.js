import matter from 'gray-matter';
import { marked } from 'marked';
function parseYamlFrontmatter(yamlStr) {
    const result = {};
    const lines = yamlStr.trim().split('\n');
    for (const line of lines) {
        const colonIndex = line.indexOf(':');
        if (colonIndex === -1)
            continue;
        const key = line.substring(0, colonIndex).trim();
        const value = line.substring(colonIndex + 1).trim();
        if (key === 'tags') {
            const tags = value.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
            if (tags.length > 0) {
                result[key] = tags;
            }
        }
        else if (value.length > 0) {
            result[key] = value;
        }
    }
    return result;
}
export async function parseMarkdown(content) {
    const result = matter(content);
    let metadata = {};
    if (typeof result.data === 'object' && result.data !== null) {
        metadata = result.data;
    }
    const html = await marked.parse(result.content);
    return {
        content: html,
        metadata
    };
}
export async function parseMarkdownWithYaml(content) {
    const fencedRegex = /^---\n([\s\S]*?)\n---\n/;
    const match = content.match(fencedRegex);
    let metadata = {};
    let markdown = content;
    if (match) {
        const yamlBlock = match[1];
        markdown = content.substring(match[0].length);
        const parsedYaml = parseYamlFrontmatter(yamlBlock);
        metadata = {
            title: parsedYaml.title,
            date: parsedYaml.date,
            tags: Array.isArray(parsedYaml.tags) ? parsedYaml.tags : undefined,
            ...Object.fromEntries(Object.entries(parsedYaml).filter(([key]) => !['title', 'date', 'tags'].includes(key)))
        };
    }
    const html = await marked.parse(markdown);
    return {
        content: html,
        metadata
    };
}
//# sourceMappingURL=parser.js.map