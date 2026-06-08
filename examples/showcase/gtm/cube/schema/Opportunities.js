cube(`Opportunities`, {
  sql: `select * from analytics_gtm.fct_gtm__opportunities`,

  measures: {
    count: {
      type: `count`,
    },
    openOpportunityCount: {
      type: `count`,
      filters: [{ sql: `${CUBE}.is_open = true` }],
    },
    wonOpportunityCount: {
      type: `count`,
      filters: [{ sql: `${CUBE}.is_won = true` }],
    },
    lostOpportunityCount: {
      type: `count`,
      filters: [{ sql: `${CUBE}.is_open = false and ${CUBE}.is_won = false` }],
    },
    openPipelineValue: {
      sql: `coalesce(${CUBE}.close_value, ${CUBE}.sales_price)`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.is_open = true` }],
    },
    forecastBaseValue: {
      sql: `coalesce(${CUBE}.close_value, ${CUBE}.sales_price)`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.is_open = true` }],
    },
    likelyForecastValue: {
      sql: `
        case
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Prospecting' then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.30
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Engaging' then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.60
          else 0
        end
      `,
      type: `sum`,
    },
    bestCaseForecastValue: {
      sql: `
        case
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Prospecting' then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.55
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Engaging' then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.85
          else 0
        end
      `,
      type: `sum`,
    },
    riskAdjustedForecastValue: {
      sql: `
        case
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Prospecting'
            then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(${CUBE}.risk_score, 0))
          when ${CUBE}.is_open = true and ${CUBE}.deal_stage = 'Engaging'
            then coalesce(${CUBE}.close_value, ${CUBE}.sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(${CUBE}.risk_score, 0))
          else 0
        end
      `,
      type: `sum`,
    },
    wonRevenue: {
      sql: `close_value`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.is_won = true` }],
    },
    averageRiskScore: {
      sql: `risk_score`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.is_open = true` }],
    },
    averageDaysSinceEngage: {
      sql: `days_since_engage`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.is_open = true` }],
    },
  },

  dimensions: {
    opportunityId: {
      sql: `opportunity_id`,
      type: `string`,
      primaryKey: true,
    },
    engageQuarter: {
      sql: `engage_quarter`,
      type: `string`,
    },
    dealStage: {
      sql: `deal_stage`,
      type: `string`,
    },
    regionalOffice: {
      sql: `regional_office`,
      type: `string`,
    },
    managerName: {
      sql: `manager_name`,
      type: `string`,
    },
    salesAgentName: {
      sql: `sales_agent_name`,
      type: `string`,
    },
    accountName: {
      sql: `account_name`,
      type: `string`,
    },
    productName: {
      sql: `product_name`,
      type: `string`,
    },
    isOpen: {
      sql: `is_open`,
      type: `boolean`,
    },
    isWon: {
      sql: `is_won`,
      type: `boolean`,
    },
  },
});
