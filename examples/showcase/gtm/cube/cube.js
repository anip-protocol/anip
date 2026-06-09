module.exports = {
  schemaPath: 'schema',
  contextToAppId: ({ securityContext }) => `gtm-showcase-${securityContext?.sub || 'anonymous'}`,
  scheduledRefreshTimer: false,
};
