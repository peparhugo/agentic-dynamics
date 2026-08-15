# SSG Plugin System Documentation

The Static Site Generator now supports a plugin system for extensibility. This allows you to hook into various stages of the build process and add custom functionality.

## Architecture

The plugin system is built on lifecycle hooks that run at different stages:

1. **onStart()** - Called at the very beginning of the build process
2. **beforeBuild()** - Called before processing any files
3. **onFile(context, file)** - Called for each file being processed
4. **afterBuild(context, pages)** - Called after all files are processed
5. **onEnd()** - Called at the very end of the build process

Each hook is optional and runs for all plugins in sequence.

## Plugin Interface

```typescript
export interface Plugin {
  name: string;
  version?: string;

  onStart?(context: PluginContext): Promise<void>;
  beforeBuild?(context: PluginContext): Promise<void>;
  onFile?(context: PluginContext, file: FileContext): Promise<void>;
  afterBuild?(context: PluginContext, pages: PageMetadata[]): Promise<void>;
  onEnd?(context: PluginContext): Promise<void>;
}
```

## Plugin Context

The `PluginContext` contains information about the build:

```typescript
export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  options?: Record<string, unknown>;
}
```

## File Context

The `FileContext` is passed to the `onFile` hook and can be mutated by plugins:

```typescript
export interface FileContext {
  filename: string;
  filePath: string;
  content: string;        // Raw file content
  parsed?: ParsedMarkdown; // Parsed markdown (set by MarkdownPlugin)
  html?: string;          // Generated HTML (set by TemplatePlugin)
  pageMetadata?: PageMetadata;
}
```

## Built-in Plugins

### MarkdownPlugin

Parses markdown files using `parseMarkdown()`. Sets `file.parsed` with the parsed markdown including frontmatter.

```typescript
import { MarkdownPlugin } from './src/plugins/index.js';

// Automatically included by default
```

### TemplatePlugin

Renders pages using templates and layouts. Sets `file.html` with the generated HTML and `file.pageMetadata` with page information.

```typescript
import { TemplatePlugin } from './src/plugins/index.js';

// Automatically included by default
```

### DevServerPlugin

Provides live reload functionality during development. Used by `DevServer` internally.

```typescript
import { DevServerPlugin } from './src/plugins/index.js';
```

## Creating Custom Plugins

To create a custom plugin, implement the `Plugin` interface:

```typescript
import { Plugin, PluginContext, FileContext } from './src/plugin.js';

export class MyCustomPlugin implements Plugin {
  name = 'my-custom-plugin';
  version = '1.0.0';

  async beforeBuild(context: PluginContext): Promise<void> {
    console.log('Build starting in:', context.contentDir);
  }

  async onFile(context: PluginContext, file: FileContext): Promise<void> {
    // Process each file
    if (file.filename.endsWith('.md')) {
      // Do something with markdown files
    }
  }

  async afterBuild(context: PluginContext, pages: PageMetadata[]): Promise<void> {
    console.log(`Generated ${pages.length} pages`);
  }
}
```

## Using Plugins with Configuration File

Create an `ssg.config.ts` file in your project root:

```typescript
import { MarkdownPlugin, TemplatePlugin } from './src/plugins/index.js';
import { MyCustomPlugin } from './src/plugins/my-custom-plugin.js';
import type { PluginConfig } from './src/plugin.js';

const config: PluginConfig = {
  plugins: [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    new MyCustomPlugin(),
  ],
};

export default config;
```

When you run the SSG, it will automatically load plugins from this configuration file.

## Using Plugins Programmatically

You can also provide plugins directly when creating a `SiteGenerator`:

```typescript
import { SiteGenerator } from './src/generator.js';
import { MyCustomPlugin } from './src/plugins/my-custom-plugin.js';

const generator = new SiteGenerator(
  {
    contentDir: './content',
    outputDir: './dist',
    templatesDir: './templates',
  },
  [new MyCustomPlugin()] // Additional plugins
);

await generator.build();
```

## Plugin Pipeline Order

Built-in plugins always run first in this order:
1. MarkdownPlugin (parses markdown)
2. TemplatePlugin (renders templates)

Then any custom plugins specified in the configuration run in order.

## Example: Analytics Plugin

Here's an example plugin that generates analytics data:

```typescript
import { Plugin, PluginContext } from './src/plugin.js';
import * as fs from 'fs';
import * as path from 'path';

export class AnalyticsPlugin implements Plugin {
  name = 'analytics';

  async afterBuild(context: PluginContext, pages: PageMetadata[]): Promise<void> {
    const analytics = {
      generatedAt: new Date().toISOString(),
      pageCount: pages.length,
      pages: pages.map(p => ({
        title: p.title,
        date: p.date,
        tags: p.tags,
      })),
    };

    const analyticsPath = path.join(context.outputDir, 'analytics.json');
    fs.writeFileSync(analyticsPath, JSON.stringify(analytics, null, 2));
  }
}
```

## Example: Custom Markdown Processing Plugin

```typescript
import { Plugin, PluginContext, FileContext } from './src/plugin.js';

export class CustomMarkdownPlugin implements Plugin {
  name = 'custom-markdown';

  async onFile(context: PluginContext, file: FileContext): Promise<void> {
    if (file.parsed && file.filename.endsWith('.md')) {
      // Add custom frontmatter processing
      if (file.parsed.frontmatter.customField) {
        console.log(`Processing custom field: ${file.parsed.frontmatter.customField}`);
      }
    }
  }
}
```

## Plugin Best Practices

1. **Use descriptive names**: Make plugin names clear about their purpose
2. **Handle errors gracefully**: Wrap operations in try-catch blocks
3. **Don't modify unrelated data**: Only modify the parts of `FileContext` your plugin is responsible for
4. **Log meaningful messages**: Help users understand what your plugin is doing
5. **Make hooks optional**: Not all plugins need all hooks
6. **Avoid side effects**: Plugins should be composable and not interfere with each other
7. **Document your plugin**: Include clear documentation about what your plugin does

## Backward Compatibility

The plugin system is designed to be completely backward compatible. Existing code that doesn't use plugins continues to work exactly as before, with the built-in plugins providing the same functionality.
