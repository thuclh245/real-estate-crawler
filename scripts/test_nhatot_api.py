import sys
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def verify_houses_category():
    url = "https://gateway.chotot.com/v1/public/ad-listing"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0",
        "Accept": "application/json, text/plain, */*",
        "X-Chotot-Platform": "IOS",
        "X-Chotot-Region": "VN",
    }
    
    # Query Houses (cg=1020) in Ha Noi (region=12)
    params = {
        "cg": "1020",
        "region": "12",
        "limit": "3",
    }
    
    print(f"Requesting API for category Houses (cg=1020)...")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ads = data.get("ads", [])
            print(f"SUCCESS! Returned {len(ads)} ads.\n")
            
            for idx, ad in enumerate(ads):
                print(f"{idx+1}. [{ad.get('ad_id')}] {ad.get('subject')}")
                print(f"   Category: {ad.get('category_name')} (cg={ad.get('category')})")
                print(f"   Price: {ad.get('price_string')} | Size: {ad.get('size')} m2")
                print("-" * 40)
        else:
            print(f"Failed with status: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_houses_category()
