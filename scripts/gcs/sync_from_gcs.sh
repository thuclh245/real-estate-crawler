#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://bigdata-subject-real-estate-lakehouse"

gcloud storage cp --recursive "$BUCKET/bronze" data/bronze
gcloud storage cp --recursive "$BUCKET/silver" data/silver
gcloud storage cp --recursive "$BUCKET/gold" data/gold
