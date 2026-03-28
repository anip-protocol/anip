# ANIP Website

This directory contains the Docusaurus site intended to become `anip.dev`.

## Purpose

The website is the public documentation and ecosystem surface for ANIP:

- why ANIP exists
- how the protocol works
- what ships today
- how to install it
- how to use Studio, showcases, transports, and validation tooling

It is intentionally kept in the main ANIP repo so the site can evolve with:

- the spec
- the release surface
- the examples
- the Studio and testing tooling

## Local development

Use Node 22 LTS or another supported Node 20-24 runtime.

```bash
cd website
npm install
npm start
```

## Production build

```bash
cd website
npm run build
npm run serve
```

The static output is written to:

```bash
website/build
```

That directory can be deployed to any static host, including:

- Cloudflare Pages
- Vercel static hosting
- Netlify
- S3 + CDN
- Nginx or Caddy behind your own edge

## CI

The repo includes a dedicated website workflow:

- `.github/workflows/ci-website.yml`

It builds the site on Node 22 whenever `website/**` changes.

## Notes

- The site is built with Docusaurus.
- The current structure is intentionally product-first:
  - strong homepage
  - docs grouped by protocol area
  - clear install and release sections
- If you are on Node 25, use Node 22 for now. Docusaurus 3.9.x is happier on the current LTS line than on bleeding-edge Node.
