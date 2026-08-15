import fs from 'fs';
import path from 'path';
import { parseMarkdownWithYaml } from '../parser.js';
import { Plugin, PageData, BuildContext } from '../plugin.js';

function slugFromFilename(filename: string): string {
  return filename.replace(/\.md$/, '');
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  constructor() {
    this.beforeBuild = this.beforeBuild.bind(this);
  }

  async beforeBuild(context: BuildContext): Promise<void> {
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

      const page: PageData = {
        slug: slugFromFilename(file),
        filename: file,
        content: parsed.content,
        metadata: parsed.metadata
      };

      pages.push(page);
    }
  }
}
