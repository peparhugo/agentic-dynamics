import type { Page } from './site.js';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export async function runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: BuildContext): Promise<void>;
export async function runHook(plugins: Plugin[], hook: 'onFile', page: Page, context: BuildContext): Promise<void>;
export async function runHook(plugins: Plugin[], hook: keyof Plugin, ...arguments_: [BuildContext] | [Page, BuildContext]): Promise<void> {
  for (const plugin of plugins) {
    if (hook === 'onFile') {
      await plugin.onFile?.(arguments_[0] as Page, arguments_[1] as BuildContext);
    } else if (hook === 'onStart') {
      await plugin.onStart?.(arguments_[0] as BuildContext);
    } else if (hook === 'beforeBuild') {
      await plugin.beforeBuild?.(arguments_[0] as BuildContext);
    } else if (hook === 'afterBuild') {
      await plugin.afterBuild?.(arguments_[0] as BuildContext);
    } else {
      await plugin.onEnd?.(arguments_[0] as BuildContext);
    }
  }
}
