type Fields = Record<string, string | number | boolean | undefined>;
const sensitive = /password|token|secret|authorization|cookie|key|body|payload|email|answer|message/i;
function write(level: 'debug' | 'info' | 'warn' | 'error', event: string, fields: Fields = {}) {
  if (level === 'debug' && process.env.NODE_ENV === 'production') return;
  const safe = Object.fromEntries(Object.entries(fields).filter(([key]) => !sensitive.test(key)));
  console[level](JSON.stringify({ timestamp: new Date().toISOString(), level, event, ...safe }));
}
export const logger = {
  debug: (event: string, fields?: Fields) => write('debug', event, fields),
  info: (event: string, fields?: Fields) => write('info', event, fields),
  warn: (event: string, fields?: Fields) => write('warn', event, fields),
  error: (event: string, fields?: Fields) => write('error', event, fields),
};
