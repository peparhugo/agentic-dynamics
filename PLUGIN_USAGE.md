# Plugin System Usage Guide

The SSG now supports a plugin system for extensibility. Plugins can hook into the build lifecycle at key points.

## Plugin Interface

All plugins must implement the `Plugin` interface:

```typescript
interface Plugin {
  name: string;
  onStart?(context: PluginContext): Promise<void> | void;
  beforeBuild?(context: PluginContext): Promise<void> | void;
  onFile?(page: PageData, context: PluginContext): Promise<void> | void;
  afterBuild?(context: PluginContext, pages: PageData[]): Promise<void> | void;
  onEnd?(context: PluginContext): Promise<void> | void;
}
```

## Lifecycle Hooks

- **onStart**: Called before the build starts
- **beforeBuild**: Called before processing files
- **onFile**: Called for each page during build
- **afterBuild**: Called after all pages are built with the list of pages
- **onEnd**: Called at the end of the build process

## Built-in Plugins

### MarkdownPlugin
Handles markdown to HTML conversion. This is a lightweight plugin that ensures markdown content is properly processed.

```typescript
import { MarkdownPlugin } from 'ssg';

const plugin = new MarkdownPlugin();
```

### TemplatePlugin
Manages Handlebars template engine initialization and setup.

```typescript
import { TemplatePlugin } from 'ssg';

const plugin = new TemplatePlugin({
  templatesDir: './templates',
  layoutsDir: './templates/layouts',
  partialsDir: './templates/partials'
});
```

### DevServerPlugin
Provides live reload development server functionality.

```typescript
import { DevServerPlugin } from 'ssg';

const plugin = new DevServerPlugin({ port: 3000 });
```

## Using the Plugin System

### With createPluginManager

```typescript
import { build, createPluginManager, MarkdownPlugin, TemplatePlugin } from 'ssg';

const manager = createPluginManager([
  new MarkdownPlugin(),
  new TemplatePlugin()
]);

await build('./content', './dist', './templates', manager);
```

### With loadPluginsFromConfig

```typescript
import { build, loadPluginsFromConfig } from 'ssg';

const manager = await loadPluginsFromConfig('./ssg.config.ts');
await build('./content', './dist', './templates', manager);
```

### Configuration File (ssg.config.ts)

```typescript
import { Plugin } from 'ssg';
import { MarkdownPlugin, TemplatePlugin, DevServerPlugin } from 'ssg';

const plugins: Plugin[] = [
  new MarkdownPlugin(),
  new TemplatePlugin(),
  new DevServerPlugin({ port: 3000 }),
];

export default { plugins };
```

## Creating Custom Plugins

```typescript
import { Plugin, PluginContext } from 'ssg';
import { PageData } from 'ssg';

export class MyCustomPlugin implements Plugin {
  name = 'my-custom-plugin';

  async onStart(context: PluginContext): Promise<void> {
    console.log('Build starting for', context.contentDir);
  }

  async onFile(page: PageData, context: PluginContext): Promise<void> {
    // Modify page data
    console.log('Processing', page.slug);
  }

  async afterBuild(context: PluginContext, pages: PageData[]): Promise<void> {
    console.log(`Built ${pages.length} pages`);
  }
}
```

## Backward Compatibility

The build system maintains full backward compatibility. The original API still works without plugins:

```typescript
import { build } from 'ssg';

// Works exactly as before
await build('./content', './dist', './templates');
```
