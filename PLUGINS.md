# SSG Plugin System

The Static Site Generator now includes a comprehensive plugin system for extending functionality and customizing the build process.

## Plugin Interface

Each plugin must implement the `Plugin` interface with a required `name` property and optional lifecycle hooks:

```typescript
interface Plugin {
  name: string;
  onStart?: (context: PluginContext) => Promise<void>;
  beforeBuild?: (context: PluginContext) => Promise<void>;
  onFile?: (page: PageData, context: PluginContext) => Promise<PageData>;
  afterBuild?: (pages: PageData[], context: PluginContext) => Promise<void>;
  onEnd?: (context: PluginContext) => Promise<void>;
}
```

## Plugin Lifecycle Hooks

### onStart
Called when the build process starts, before any files are read.

**Use case:** Initialize resources, load configurations, set up cache

```typescript
onStart: async (context: PluginContext) => {
  console.log(`Starting build: ${context.contentDir}`);
}
```

### beforeBuild
Called after files are read but before they are processed.

**Use case:** Load templates, register partials, prepare data

```typescript
beforeBuild: async (context: PluginContext) => {
  await loadPartials(context.templateDir);
}
```

### onFile
Called for each markdown file during processing. Can modify page data.

**Use case:** Transform content, add metadata, apply templates

```typescript
onFile: async (page: PageData, context: PluginContext) => {
  return {
    ...page,
    html: page.html + '<!-- processed -->'
  };
}
```

### afterBuild
Called after all pages have been generated.

**Use case:** Generate sitemaps, create indexes, compile assets

```typescript
afterBuild: async (pages: PageData[], context: PluginContext) => {
  console.log(`Generated ${pages.length} pages`);
}
```

### onEnd
Called when the build process completes.

**Use case:** Clean up resources, log statistics, notify services

```typescript
onEnd: async (context: PluginContext) => {
  console.log('Build process complete');
}
```

## Built-in Plugins

### MarkdownPlugin
Handles markdown file processing.
- Location: `src/plugins/markdown.plugin.ts`
- Hooks: `onFile`

### TemplatePlugin
Applies Handlebars templates and layouts to pages.
- Location: `src/plugins/template.plugin.ts`
- Hooks: `beforeBuild`, `onFile`

### DevServerPlugin
Provides live-reload development server functionality.
- Location: `src/plugins/dev-server.plugin.ts`
- Hooks: `onStart`, `onEnd`

## Creating a Custom Plugin

### Simple Plugin Example

```typescript
import { Plugin, PluginContext } from './plugin';
import { PageData } from './page';

export const MyPlugin: Plugin = {
  name: 'my-plugin',

  onFile: async (page: PageData, context: PluginContext) => {
    // Add custom metadata
    return {
      ...page,
      customField: 'custom value'
    };
  }
};
```

### Plugin That Transforms Content

```typescript
export const SyntaxHighlightPlugin: Plugin = {
  name: 'syntax-highlight',

  onFile: async (page: PageData, context: PluginContext) => {
    // Transform code blocks
    const transformedHtml = page.html.replace(
      /<pre><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g,
      (match, lang, code) => {
        return `<pre class="hljs language-${lang}"><code>${highlight(code, lang)}</code></pre>`;
      }
    );

    return {
      ...page,
      html: transformedHtml
    };
  }
};
```

## Configuration

### Using Plugins Programmatically

```typescript
import { PluginManager } from './plugin';
import { build } from './build';
import { MarkdownPlugin } from './plugins/markdown.plugin';
import { TemplatePlugin } from './plugins/template.plugin';

const manager = new PluginManager();
manager.register(MarkdownPlugin);
manager.register(TemplatePlugin);

// Manager handles plugin lifecycle
```

### Configuration File

Create `ssg.config.ts`:

```typescript
import { SSGConfig } from './src/config';
import { MarkdownPlugin } from './src/plugins/markdown.plugin';
import { TemplatePlugin } from './src/plugins/template.plugin';

const config: SSGConfig = {
  contentDir: './content',
  outputDir: './dist',
  templateDir: './templates',
  plugins: [
    MarkdownPlugin,
    TemplatePlugin,
  ]
};

export default config;
```

## PluginContext

The context object passed to all hooks provides:

```typescript
interface PluginContext {
  contentDir: string;        // Directory containing markdown files
  outputDir: string;         // Directory for generated HTML
  templateDir?: string;      // Directory containing templates
}
```

## Best Practices

1. **Error Handling**: Plugins should handle errors gracefully
   ```typescript
   onFile: async (page, context) => {
     try {
       // process
     } catch (error) {
       console.error(`Plugin error: ${error.message}`);
       return page; // return unmodified page
     }
   }
   ```

2. **Plugin Order**: Order matters! Later plugins see results from earlier ones
   ```typescript
   manager.register(MarkdownPlugin);      // runs first
   manager.register(TemplatePlugin);      // runs second
   manager.register(CustomPlugin);        // runs third
   ```

3. **Immutability**: Don't mutate page objects directly
   ```typescript
   // Good
   return { ...page, title: newTitle };
   
   // Avoid
   page.title = newTitle;
   return page;
   ```

4. **Performance**: Keep hooks fast, especially `onFile` which runs per page
   - Cache expensive operations in `beforeBuild`
   - Use `onFile` only for lightweight transformations

5. **Documentation**: Document what your plugin does and how to use it
   ```typescript
   export const MyPlugin: Plugin = {
     name: 'my-plugin',
     // Adds statistics to each page
     // Usage: no configuration needed
     onFile: async (page) => { ... }
   };
   ```

## Examples

### Logging Plugin

```typescript
export const LoggingPlugin: Plugin = {
  name: 'logging',
  onStart: async (context) => {
    console.log(`[Logging] Build started`);
  },
  onFile: async (page, context) => {
    console.log(`[Logging] Processing: ${page.slug}`);
    return page;
  },
  afterBuild: async (pages, context) => {
    console.log(`[Logging] ${pages.length} pages generated`);
  }
};
```

### Metadata Plugin

```typescript
export const MetadataPlugin: Plugin = {
  name: 'metadata',
  onFile: async (page, context) => {
    return {
      ...page,
      generatedAt: new Date().toISOString(),
      wordCount: page.html.split(/\s+/).length
    };
  }
};
```

## Backward Compatibility

The plugin system maintains full backward compatibility with existing code:

- Existing API (build, generatePageHtml, etc.) works unchanged
- Plugins are optional - build works without them
- Legacy templates and markdown processing unchanged

## Testing Plugins

```typescript
import { PluginManager } from './plugin';

const manager = new PluginManager();
manager.register(MyPlugin);

const page = { slug: 'test', title: 'Test', html: '<p>Test</p>' };
const context = { contentDir: './content', outputDir: './dist' };

const result = await manager.runOnFile(page, context);
expect(result).toBeDefined();
```
