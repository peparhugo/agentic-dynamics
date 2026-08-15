# Plugin System Architecture

## Overview

The SSG has been refactored to use a plugin system for extensibility. The plugin architecture enables:

- Modular feature implementation
- Easy addition of new functionality
- Clean separation of concerns
- Extensibility without modifying core engine

## Plugin Interface

```typescript
interface Plugin {
  name: string;
  onStart?(context: BuildContext): Promise<void>;
  beforeBuild?(context: BuildContext): Promise<void>;
  onFile?(page: PageData, context: BuildContext): Promise<void>;
  afterBuild?(context: BuildContext): Promise<void>;
  onEnd?(context: BuildContext): Promise<void>;
}
```

### Lifecycle Hooks

- **onStart**: Called before building starts (e.g., server initialization)
- **beforeBuild**: Called before processing markdown files (e.g., setup)
- **onFile**: Called for each page being processed (e.g., page rendering)
- **afterBuild**: Called after all pages are processed (e.g., index generation)
- **onEnd**: Called when the build process ends (e.g., cleanup)

## Built-in Plugins

### MarkdownPlugin
- Reads markdown files from content directory
- Parses YAML frontmatter
- Converts markdown to HTML
- Populates pages array in BuildContext

### TemplatePlugin
- Initializes template engine
- Renders each page with layouts
- Generates index.html
- Ensures default templates exist

### DevServerPlugin
- Starts HTTP server
- Provides WebSocket live reload
- Watches for file changes
- Triggers rebuilds on changes

## Plugin Manager

The `PluginManager` orchestrates the plugin pipeline:

```typescript
class PluginManager {
  addPlugin(plugin: Plugin): void;
  async callHook(hookName, context, page?): Promise<void>;
  getPlugins(): Plugin[];
}
```

The plugin manager executes hooks in order, allowing plugins to build on previous work.

## Build Context

Plugins communicate through the `BuildContext` object:

```typescript
interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
  pages: PageData[];
  [key: string]: any;  // Extensible for custom data
}
```

## Configuration

Plugins are configured in `ssg.config.ts`:

```typescript
import { Plugin } from './src/plugin.js';
import { MarkdownPlugin } from './src/plugins/markdown-plugin.js';
import { TemplatePlugin } from './src/plugins/template-plugin.js';

export function getDefaultPlugins(): Plugin[] {
  return [
    new MarkdownPlugin(),
    new TemplatePlugin()
  ];
}

export async function loadPlugins(configPath?: string): Promise<Plugin[]> {
  // Load plugins from config or return defaults
}
```

## Creating Custom Plugins

Example custom plugin:

```typescript
import { Plugin, BuildContext, PageData } from './plugin.js';

export class CustomPlugin implements Plugin {
  name = 'custom';

  constructor(private options: any = {}) {
    this.beforeBuild = this.beforeBuild.bind(this);
  }

  async beforeBuild(context: BuildContext): Promise<void> {
    // Custom setup logic
  }

  async onFile(page: PageData, context: BuildContext): Promise<void> {
    // Process each page
  }

  async afterBuild(context: BuildContext): Promise<void> {
    // Post-processing
  }
}
```

## Generator Refactoring

The new generator is simplified and plugin-driven:

```typescript
export async function generate(options: GeneratorOptions): Promise<void> {
  const pluginManager = new PluginManager();
  pluginManager.addPlugin(new MarkdownPlugin());
  pluginManager.addPlugin(new TemplatePlugin());

  const context: BuildContext = {
    contentDir,
    outputDir,
    pages: []
  };

  await pluginManager.callHook('onStart', context);
  await pluginManager.callHook('beforeBuild', context);

  for (const page of context.pages) {
    await pluginManager.callHook('onFile', context, page);
  }

  await pluginManager.callHook('afterBuild', context);
  await pluginManager.callHook('onEnd', context);
}
```

## External API Compatibility

The external API remains identical:
- `generate(options)` - Same function signature and behavior
- `serve(options, test)` - Same function signature and behavior
- CLI commands unchanged

All 65 existing tests pass without modification.

## File Structure

```
src/
├── plugin.ts              # Plugin interface and manager
├── plugins/
│   ├── markdown-plugin.ts
│   ├── template-plugin.ts
│   └── dev-server-plugin.ts
├── generator.ts           # Refactored to use plugins
├── serve.ts              # Refactored to use plugins
├── parser.ts             # Unchanged
├── template.ts           # Unchanged
├── cli.ts                # Unchanged
└── index.ts              # Unchanged

ssg.config.ts            # Plugin configuration file
```

## Benefits

1. **Modularity**: Each feature is isolated in its own plugin
2. **Extensibility**: New features can be added without modifying core
3. **Testability**: Plugins can be tested independently
4. **Flexibility**: Plugins can be enabled/disabled via configuration
5. **Backward Compatibility**: External API unchanged, all tests pass
