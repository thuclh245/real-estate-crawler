import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transform.silver_to_gold.spark_session import create_spark


class SparkSessionConfigTest(unittest.TestCase):
    def test_spark_session_reads_resource_env_vars(self):
        previous_env = {
            key: os.environ.get(key)
            for key in [
                "SPARK_MASTER",
                "SPARK_DRIVER_MEMORY",
                "SPARK_DRIVER_MAX_RESULT_SIZE",
                "SPARK_SQL_SHUFFLE_PARTITIONS",
                "SPARK_DEFAULT_PARALLELISM",
            ]
        }
        os.environ["SPARK_MASTER"] = "local[1]"
        os.environ["SPARK_DRIVER_MEMORY"] = "2g"
        os.environ["SPARK_DRIVER_MAX_RESULT_SIZE"] = "512m"
        os.environ["SPARK_SQL_SHUFFLE_PARTITIONS"] = "3"
        os.environ["SPARK_DEFAULT_PARALLELISM"] = "3"

        spark = create_spark()
        try:
            self.assertEqual(spark.sparkContext.master, "local[1]")
            self.assertEqual(spark.conf.get("spark.driver.memory"), "2g")
            self.assertEqual(spark.conf.get("spark.driver.maxResultSize"), "512m")
            self.assertEqual(spark.conf.get("spark.sql.shuffle.partitions"), "3")
            self.assertEqual(spark.conf.get("spark.default.parallelism"), "3")
        finally:
            spark.stop()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
