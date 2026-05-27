import sys
from pathlib import Path

# Add src to PYTHONPATH
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from transform.bronze_to_silver import run_bronze_to_silver

def main():
    bronze_base = Path("data/bronze")
    silver_base = Path("data/silver")
    
    print("=== RUNNING BRONZE-TO-SILVER TRANSFORMATION ===")
    
    # Glob all bronze metadata folders (source=*/crawl_date=*/crawl_id=*/metadata)
    metadata_folders = list(bronze_base.glob("source=*/crawl_date=*/crawl_id=*/metadata"))
    
    if not metadata_folders:
        print("Không tìm thấy thư mục phân vùng nào dưới data/bronze.")
        return
        
    for meta_folder in metadata_folders:
        bronze_dir = meta_folder.parent
        rel_path = bronze_dir.relative_to(bronze_base)
        silver_dir = silver_base / rel_path
        
        print(f"\nĐang chuyển đổi: {rel_path}")
        try:
            # Xác định parser dựa trên nguồn dữ liệu
            source = rel_path.parts[0].split("=")[1]
            parser_version = "nhatot_adapter_v0.1" if source == "nhatot" else "phase2_v1"
            
            run_bronze_to_silver(
                bronze_dir=str(bronze_dir),
                silver_dir=str(silver_dir),
                parser_version=parser_version
            )
            print(f"✓ Hoàn thành: {silver_dir}")
        except Exception as e:
            print(f"✗ Thất bại cho {bronze_dir}: {e}")

if __name__ == "__main__":
    main()
