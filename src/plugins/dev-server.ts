import { Plugin } from '../plugin';
import { DevServer, DevServerOptions } from '../dev-server';

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  createServer(options: DevServerOptions): DevServer {
    return new DevServer(options);
  }
}
