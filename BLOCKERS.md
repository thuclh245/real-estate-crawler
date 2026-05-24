# Blockers

## Silver to Gold on Windows

`python src/transform/silver_to_gold.py` currently fails in this Windows environment at the first Parquet write because Spark/Hadoop cannot find `winutils.exe` (`HADOOP_HOME` / `hadoop.home.dir` are unset).

Status:
- `python -m pytest tests --tb=short` passes
- Package split and shim load correctly
- Full Gold write path needs a Windows Hadoop setup or a Linux/WSL validation environment
