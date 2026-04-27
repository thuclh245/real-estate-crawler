#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://bigdata-subject-real-estate-lakehouse"

gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/bronze" data/bronze
gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/silver" data/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/gold" data/gold
