import { marked } from 'marked';
import matter from 'gray-matter';
// Note: .js extensions are required for ES modules
function parseYamlFrontmatter(yamlString) {
    const frontmatter = {};
    const lines = yamlString.split('\n');
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#'))
            continue;
        const colonIndex = trimmed.indexOf(':');
        if (colonIndex === -1)
            continue;
        const key = trimmed.substring(0, colonIndex).trim();
        const valueStr = trimmed.substring(colonIndex + 1).trim();
        if (key === 'tags') {
            if (valueStr) {
                frontmatter.tags = valueStr
                    .split(',')
                    .map((tag) => tag.trim())
                    .filter((tag) => tag.length > 0);
            }
            else {
                frontmatter.tags = [];
            }
        }
        else if (key === 'title' || key === 'date') {
            frontmatter[key] = valueStr.replace(/^["']|["']$/g, '');
        }
        else if (valueStr) {
            frontmatter[key] = valueStr;
        }
    }
    return frontmatter;
}
export async function parseMarkdown(content) {
    let frontmatter = {};
    let markdownContent = content;
    // Try to parse YAML frontmatter manually first
    if (content.startsWith('---')) {
        const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
        if (match) {
            const yamlBlock = match[1];
            frontmatter = parseYamlFrontmatter(yamlBlock);
            markdownContent = match[2];
        }
    }
    else {
        // If no manual YAML, try gray-matter
        const matterResult = matter(content);
        frontmatter = matterResult.data;
        markdownContent = matterResult.content;
        // Convert any arrays to tags if needed
        if (frontmatter.tags && !Array.isArray(frontmatter.tags)) {
            if (typeof frontmatter.tags === 'string') {
                frontmatter.tags = frontmatter.tags
                    .split(',')
                    .map((tag) => tag.trim())
                    .filter((tag) => tag.length > 0);
            }
        }
    }
    const html = await marked(markdownContent);
    return {
        frontmatter,
        content: markdownContent,
        html: html,
    };
}
//# sourceMappingURL=parser.js.map