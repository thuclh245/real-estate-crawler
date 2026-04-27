#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://bigdata-subject-real-estate-lakehouse"

gcloud storage rsync --recursive --exclude=".*\.crc$" data/bronze "$BUCKET/bronze"
gcloud storage rsync --recursive --exclude=".*\.crc$" data/silver "$BUCKET/silver"
gcloud storage rsync --recursive --exclude=".*\.crc$" data/gold "$BUCKET/gold"
