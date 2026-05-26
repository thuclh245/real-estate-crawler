import sys
import requests
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_10_listings():
    url = "https://gateway.chotot.com/v1/public/ad-listing"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0",
        "Accept": "application/json, text/plain, */*",
        "X-Chotot-Platform": "IOS",
        "X-Chotot-Region": "VN",
    }
    
    # Fetch 10 real estate listings in Ha Noi
    params = {
        "cg": "1000",       # Bất động sản nói chung
        "region": "12",     # Hà Nội
        "limit": "10",      # 10 listings
    }
    
    print("Fetching 10 listings from Chợ Tốt Mobile API...")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            ads = data.get("ads", [])
            print(f"SUCCESS! Retrieved {len(ads)} ads.\n")
            
            for idx, ad in enumerate(ads):
                # Process values politely
                ad_id = ad.get("ad_id") or ad.get("list_id")
                title = ad.get("subject", "N/A")
                price = ad.get("price_string", "N/A")
                size = ad.get("size", "N/A")
                
                ward = ad.get("ward_name", "")
                district = ad.get("area_name", "")
                city = ad.get("region_name", "")
                full_address = ", ".join(filter(None, [ad.get("street_name"), ward, district, city]))
                
                rooms = ad.get("rooms", "N/A")
                toilets = ad.get("toilets", "N/A")
                gps = f"{ad.get('latitude')}, {ad.get('longitude')}" if ad.get('latitude') else "N/A"
                project = ad.get("pty_project_name", "Không thuộc dự án")
                
                description = ad.get("body") or "N/A"
                # Indent lines of description for nice layout
                description_clean = "\n                ".join(description.splitlines())
                
                web_url = f"https://www.nhatot.com/{ad.get('category_slug', 'mua-ban-nha-dat')}/{ad_id}.htm"
                
                print(f"📌 TIN ĐĂNG #{idx+1:02d} [Mã tin: {ad_id}]")
                print(f"  - Tiêu đề   : {title}")
                print(f"  - Giá bán   : {price}")
                # We show raw price in VND as well to show data completeness
                print(f"  - Giá trị số: {ad.get('price')} VND")
                print(f"  - Diện tích : {size} m²")
                print(f"  - Địa chỉ   : {full_address}")
                print(f"  - Dự án     : {project}")
                print(f"  - Phòng ngủ : {rooms} | WC: {toilets}")
                print(f"  - Tọa độ GPS: {gps}")
                print(f"  - Mô tả     : {description_clean}")
                print(f"  - Link Web  : {web_url}")
                print("-" * 70)
        else:
            print(f"Failed to fetch. HTTP Status: {response.status_code}")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    get_10_listings()
