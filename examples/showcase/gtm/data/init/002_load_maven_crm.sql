truncate table raw_gtm.accounts;
truncate table raw_gtm.products;
truncate table raw_gtm.sales_teams;
truncate table raw_gtm.sales_pipeline;

\copy raw_gtm.accounts from '/seed/raw/maven/accounts.csv' with (format csv, header true);
\copy raw_gtm.products from '/seed/raw/maven/products.csv' with (format csv, header true);
\copy raw_gtm.sales_teams from '/seed/raw/maven/sales_teams.csv' with (format csv, header true);
\copy raw_gtm.sales_pipeline from '/seed/raw/maven/sales_pipeline.csv' with (format csv, header true);
