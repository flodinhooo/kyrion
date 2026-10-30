// Next dev propagates runtime flags into NODE_OPTIONS for its child process.
// --env-file is forbidden there; an allowed preload preserves native .env parsing.
if (process.env.KYRION_WEB_CONFIG_FILE) process.loadEnvFile(process.env.KYRION_WEB_CONFIG_FILE);
