cube(`PipelineHealth`, {
  sql: `select * from analytics_gtm.mart_gtm__pipeline_health`,

  measures: {
    opportunityCount: {
      sql: `opportunity_count`,
      type: `sum`,
    },
    openOpportunityCount: {
      sql: `open_opportunity_count`,
      type: `sum`,
    },
    wonOpportunityCount: {
      sql: `won_opportunity_count`,
      type: `sum`,
    },
    lostOpportunityCount: {
      sql: `lost_opportunity_count`,
      type: `sum`,
    },
    wonRevenue: {
      sql: `won_revenue`,
      type: `sum`,
    },
    openPipelineValue: {
      sql: `open_pipeline_value`,
      type: `sum`,
    },
    averageOpenRiskScore: {
      sql: `average_open_risk_score`,
      type: `avg`,
    },
    averageOpenDays: {
      sql: `average_open_days`,
      type: `avg`,
    },
  },

  dimensions: {
    engageQuarter: {
      sql: `engage_quarter`,
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
    dealStage: {
      sql: `deal_stage`,
      type: `string`,
    },
  },
});
