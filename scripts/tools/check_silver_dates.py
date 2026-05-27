import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from transform.silver_to_gold.spark_session import create_spark
from transform.silver_to_gold.reader import read_silver

def main():
    spark = create_spark()
    try:
        print("=== READING SILVER ===")
        df = read_silver(spark, "data/silver")
        
        print("=== DATA SUMMARY (SOURCE & CRAWL_DATE) ===")
        df.groupBy("source", "crawl_date").count().orderBy("source", "crawl_date").show(100, truncate=False)
        
        print("=== UNIQUE DATES ===")
        df.select("crawl_date").distinct().orderBy("crawl_date").show(100, truncate=False)
        
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
