# Plugin System Architecture

## Overview

The SSG has been refactored to use a plugin system for extensibility. The architecture allows existing features (markdown, templates, dev server) to be implemented as built-in plugins, while enabling users to create custom plugins.

## Architecture

```
┌─────────────────────────────────────────┐
│         CLI / Build Entry Point         │
│  (src/cli.ts, build() function)         │
└────────────┬────────────────────────────┘
             │
             ├─► Loads config (optional)
             │
             ▼
┌─────────────────────────────────────────┐
│       PluginManager                     │
│  - Manages plugin lifecycle             │
│  - Orchestrates hook execution          │
└────────────┬────────────────────────────┘
             │
             ├─► onStart hook
             ├─► beforeBuild hook
             ├─► onFile hook (per page)
             ├─► afterBuild hook
             └─► onEnd hook
             │
             ▼
┌─────────────────────────────────────────┐
│      Built-in Plugins                   │
│  ┌─────────────────────────────────────┐│
│  │ MarkdownPlugin                      ││
│  │  - Lightweight markdown handler     ││
│  ├─────────────────────────────────────┤│
│  │ TemplatePlugin                      ││
│  │  - Handlebars template setup        ││
│  ├─────────────────────────────────────┤│
│  │ DevServerPlugin                     ││
│  │  - Live reload development server   ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
```

## File Structure

```
src/
├── plugin.ts                 # Plugin interface and PluginManager
├── plugin-loader.ts          # Plugin loading utilities
├── plugins/
│   ├── index.ts             # Plugin exports
│   ├── markdown-plugin.ts    # Markdown processing plugin
│   ├── template-plugin.ts    # Template engine plugin
│   └── dev-server-plugin.ts  # Dev server plugin
├── generator.ts             # Updated to support plugins
├── index.ts                 # Updated exports
└── plugin-system.test.ts    # Plugin system tests

ssg.config.ts               # Example configuration file
```

## Plugin Lifecycle

### 1. onStart Hook
- **When**: Before any build processing
- **Use**: Initialize plugins, load configuration
- **Access**: `PluginContext` (contentDir, outputDir, templatesDir)

### 2. beforeBuild Hook
- **When**: Before files are processed
- **Use**: Pre-build validation, data preparation
- **Access**: `PluginContext`

### 3. onFile Hook
- **When**: For each page being processed
- **Use**: Transform page data, modify HTML, add metadata
- **Access**: `PageData` and `PluginContext`

### 4. afterBuild Hook
- **When**: After all pages are built
- **Use**: Post-processing, validation, cleanup
- **Access**: `PluginContext` and full `PageData[]` array

### 5. onEnd Hook
- **When**: At the very end
- **Use**: Final cleanup, reporting
- **Access**: `PluginContext`

## Implementation Details

### PluginManager

The `PluginManager` class orchestrates plugin execution:

```typescript
class PluginManager {
  addPlugin(plugin: Plugin): void;
  async executeHook(hookName, context, pages?): Promise<void>;
  async executeFileHook(page, context): Promise<void>;
  getPlugins(): Plugin[];
  getPlugin(name): Plugin | undefined;
}
```

### Built-in Plugins

#### MarkdownPlugin
- Name: `'markdown-plugin'`
- Hooks: None (markdown conversion is handled in parseMarkdownFile)
- Purpose: Placeholder for markdown-related functionality

#### TemplatePlugin
- Name: `'template-plugin'`
- Hooks: onStart
- Options: templatesDir, layoutsDir, partialsDir
- Purpose: Initializes Handlebars template engine

#### DevServerPlugin
- Name: `'dev-server-plugin'`
- Hooks: onStart, afterBuild
- Options: port
- Purpose: Starts live reload dev server

## Backward Compatibility

The plugin system maintains 100% backward compatibility:

```typescript
// Old API - still works exactly as before
await build('./content', './dist', './templates');

// New API - with plugins
const manager = createPluginManager([
  new MarkdownPlugin(),
  new TemplatePlugin(),
]);
await build('./content', './dist', './templates', manager);
```

## Creating Custom Plugins

Users can create custom plugins by implementing the `Plugin` interface:

```typescript
import { Plugin, PluginContext, PageData } from 'ssg';

export class MyPlugin implements Plugin {
  name = 'my-plugin';

  async onStart(context: PluginContext): Promise<void> {
    console.log('Build starting');
  }

  async onFile(page: PageData, context: PluginContext): Promise<void> {
    // Modify page data
    if (page.frontmatter.featured) {
      page.html += '<div class="featured-badge">Featured</div>';
    }
  }

  async afterBuild(context: PluginContext, pages: PageData[]): Promise<void> {
    console.log(`Built ${pages.length} pages`);
  }
}
```

## Configuration

Plugins can be configured via `ssg.config.ts`:

```typescript
import { Plugin } from 'ssg';
import { MarkdownPlugin, TemplatePlugin, DevServerPlugin } from 'ssg';

const plugins: Plugin[] = [
  new MarkdownPlugin(),
  new TemplatePlugin({
    templatesDir: './templates',
  }),
  new DevServerPlugin({ port: 3000 }),
];

export default { plugins };
```

## Testing

The plugin system includes comprehensive tests:
- Plugin manager functionality
- Plugin lifecycle execution
- Built-in plugin behavior
- Backward compatibility
- Multiple page handling

All 93 tests pass (88 existing + 5 plugin tests).

## Extensibility Points

The plugin system enables:
1. Custom markdown processors
2. Additional template engines
3. Build event tracking and logging
4. SEO optimization (meta tags, sitemaps)
5. Asset processing and optimization
6. Static site generation analytics
7. Custom development servers
8. Pre/post-build validation

## Migration Guide

### Existing Users
No migration needed. Your existing code continues to work without changes.

### Adopting Plugins
To start using the plugin system:

1. Create a `ssg.config.ts` file
2. Import plugins and create instances
3. Pass the plugin manager to the `build()` function

```typescript
import { build, createPluginManager, MarkdownPlugin, TemplatePlugin } from 'ssg';

const manager = createPluginManager([
  new MarkdownPlugin(),
  new TemplatePlugin(),
]);

await build('./content', './dist', './templates', manager);
```
