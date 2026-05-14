from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("CheckGold")
    .master("local[*]")
    .config("spark.driver.bindAddress", "127.0.0.1")
    .config("spark.driver.host", "127.0.0.1")
    .getOrCreate()
)

tables = [
    "gold_current_listings",
    "gold_listing_snapshots",
    "gold_market_by_district_daily",
    "gold_data_quality_daily",
    "gold_removed_listings",
]

for table in tables:
    path = f"data/gold/{table}"
    print(f"\n=== {table} ===")
    df = spark.read.parquet(path)
    print("count:", df.count())
    df.printSchema()
    df.show(10, truncate=False)

spark.stop()