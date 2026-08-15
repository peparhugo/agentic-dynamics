import { SiteGenerator } from './generator.js';
import { DevServerPlugin } from './plugins/dev-server-plugin.js';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
}

export class DevServer {
  private contentDir: string;
  private outputDir: string;
  private templatesDir: string;
  private port: number;
  private generator: SiteGenerator;
  private devServerPlugin: DevServerPlugin;

  constructor(options: DevServerOptions) {
    this.contentDir = options.contentDir;
    this.outputDir = options.outputDir;
    this.templatesDir = options.templatesDir || './templates';
    this.port = options.port || 3000;

    this.generator = new SiteGenerator({
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
    });

    this.devServerPlugin = new DevServerPlugin({
      port: this.port,
      onRebuild: async () => {
        await this.generator.build();
      },
    });
  }

  async start(): Promise<void> {
    // Initial build
    await this.generator.build();

    // Start dev server with live reload
    const pluginContext = {
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
    };

    await this.devServerPlugin.onStart(pluginContext);

    return new Promise(() => {
      // This promise never resolves while the server is running
    });
  }

  async stop(): Promise<void> {
    await this.devServerPlugin.stop();
  }

  private injectLiveReloadScript(html: string): string {
    const liveReloadScript = `
<script>
(function() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(protocol + '//' + window.location.host);

  ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    if (message.type === 'reload') {
      console.log('[Live Reload] Reloading page...');
      window.location.reload();
    }
  };

  ws.onerror = function(error) {
    console.error('[Live Reload] WebSocket error:', error);
  };

  ws.onopen = function() {
    console.log('[Live Reload] Connected');
  };
})();
</script>
`;
    return html.replace('</body>', liveReloadScript + '</body>');
  }
}
