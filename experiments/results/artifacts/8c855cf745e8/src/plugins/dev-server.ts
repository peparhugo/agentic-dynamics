import type { Plugin } from '../plugin';

/** Marker plugin for integrations that provide a development server. */
export function DevServerPlugin(): Plugin {
  return { name: 'dev-server' };
}

export default DevServerPlugin;
