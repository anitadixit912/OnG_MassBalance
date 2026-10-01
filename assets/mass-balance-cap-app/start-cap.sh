#!/bin/sh
# Use the [docker] CDS profile: SQLite file DB + dummy auth (no HANA, no XSUAA)
export CDS_ENV=docker
exec /cap/node_modules/.bin/cds-serve
