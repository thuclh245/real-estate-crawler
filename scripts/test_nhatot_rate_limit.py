import sys
import time
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_rate_limit_test():
    url = "https://gateway.chotot.com/v1/public/ad-listing"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0",
        "Accept": "application/json, text/plain, */*",
        "X-Chotot-Platform": "IOS",
        "X-Chotot-Region": "VN",
    }
    
    params = {
        "cg": "1010",
        "region": "12",
        "limit": "3",
    }
    
    print("="*60)
    print("STARTING CONTROLLED RATE LIMIT & ROBUSTNESS TEST")
    print("="*60)
    
    # ----------------------------------------------------
    # TEST 1: Burst Test - 10 Requests with 0s Delay
    # ----------------------------------------------------
    print("\n[TEST 1] BURST TEST: 10 requests in rapid succession (0s delay)")
    success_t1 = 0
    start_t1 = time.perf_counter()
    
    for i in range(1, 11):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                success_t1 += 1
                print(f"  Request {i:02d}: SUCCESS (200 OK) - Length: {len(res.text)} bytes")
            elif res.status_code == 429:
                print(f"  Request {i:02d}: RATE LIMITED (429 Too Many Requests) ❌")
            else:
                print(f"  Request {i:02d}: HTTP {res.status_code} ⚠️")
        except Exception as e:
            print(f"  Request {i:02d}: Error: {e} ❌")
            
    dur_t1 = time.perf_counter() - start_t1
    print(f"--> Test 1 Results: {success_t1}/10 successful. Total time: {dur_t1:.2f}s")
    
    # Let the API breathe for 5 seconds before next test
    print("\nWaiting 5 seconds for system cooling...")
    time.sleep(5)
    
    # ----------------------------------------------------
    # TEST 2: Fast Test - 10 Requests with 0.5s Delay
    # ----------------------------------------------------
    print("\n[TEST 2] FAST TEST: 10 requests with 0.5s delay")
    success_t2 = 0
    start_t2 = time.perf_counter()
    
    for i in range(1, 11):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                success_t2 += 1
                print(f"  Request {i:02d}: SUCCESS (200 OK)")
            elif res.status_code == 429:
                print(f"  Request {i:02d}: RATE LIMITED (429) ❌")
            else:
                print(f"  Request {i:02d}: HTTP {res.status_code} ⚠️")
        except Exception as e:
            print(f"  Request {i:02d}: Error: {e} ❌")
        time.sleep(0.5)
            
    dur_t2 = time.perf_counter() - start_t2
    print(f"--> Test 2 Results: {success_t2}/10 successful. Total time: {dur_t2:.2f}s")
    
    # Let the API breathe for 5 seconds
    print("\nWaiting 5 seconds for system cooling...")
    time.sleep(5)
    
    # ----------------------------------------------------
    # TEST 3: Safe Crawler Test - 10 Requests with 1.0s Delay
    # ----------------------------------------------------
    print("\n[TEST 3] CRAWLER SIMULATION: 10 requests with 1.0s delay")
    success_t3 = 0
    start_t3 = time.perf_counter()
    
    for i in range(1, 11):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                success_t3 += 1
                print(f"  Request {i:02d}: SUCCESS (200 OK)")
            elif res.status_code == 429:
                print(f"  Request {i:02d}: RATE LIMITED (429) ❌")
            else:
                print(f"  Request {i:02d}: HTTP {res.status_code} ⚠️")
        except Exception as e:
            print(f"  Request {i:02d}: Error: {e} ❌")
        time.sleep(1.0)
            
    dur_t3 = time.perf_counter() - start_t3
    print(f"--> Test 3 Results: {success_t3}/10 successful. Total time: {dur_t3:.2f}s")
    
    print("\n" + "="*60)
    print("CONCLUSION & RECOMMENDATION")
    print("="*60)
    if success_t1 == 10:
        print("🎉 EXCELLENT: Even burst requests with 0s delay were not rate-limited!")
        print("   This API is highly robust and forgiving.")
    elif success_t2 == 10:
        print("✅ VERY GOOD: 0.5s delay is completely safe for production.")
    elif success_t3 == 10:
        print("ℹ️ STABLE: 1.0s delay is completely safe.")
    else:
        print("⚠️ WARNING: Rate limiting detected. We must use a delay of at least 1.5s and proxies.")

if __name__ == "__main__":
    run_rate_limit_test()
