$BUCKET = "gs://bigdata-subject-real-estate-lakehouse"

gcloud storage cp --recursive data/bronze "$BUCKET/bronze"
gcloud storage cp --recursive data/silver "$BUCKET/silver"
gcloud storage cp --recursive data/gold "$BUCKET/gold"
