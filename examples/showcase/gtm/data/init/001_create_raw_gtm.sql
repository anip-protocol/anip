create schema if not exists raw_gtm;

create table if not exists raw_gtm.accounts (
    account text primary key,
    sector text,
    year_established integer,
    revenue numeric(18, 2),
    employees integer,
    office_location text,
    subsidiary_of text
);

create table if not exists raw_gtm.products (
    product text primary key,
    series text,
    sales_price numeric(18, 2)
);

create table if not exists raw_gtm.sales_teams (
    sales_agent text primary key,
    manager text,
    regional_office text
);

create table if not exists raw_gtm.sales_pipeline (
    opportunity_id text primary key,
    sales_agent text,
    product text,
    account text,
    deal_stage text,
    engage_date date,
    close_date date,
    close_value numeric(18, 2)
);

create schema if not exists analytics_gtm;
