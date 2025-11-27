import asyncio
import httpx
import time
import sys
import os

# ANSI Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

async def test_connection(name, url):
    print(f"Testing {name}...", end=" ", flush=True)
    start = time.time()
    try:
        # We mimic a browser to avoid being blocked by anti-bot protections
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Test/1.0"}
        
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            resp = await client.get(url)
            duration = round((time.time() - start) * 1000, 2)
            
            if resp.status_code == 200:
                print(f"{GREEN}SUCCESS{RESET} ({duration}ms) - Status: 200")
                return True
            else:
                print(f"{RED}FAILED{RESET} - Status Code: {resp.status_code}")
                return False
                
    except httpx.ConnectTimeout:
        print(f"{RED}TIMEOUT{RESET} - Server took too long to respond (Firewall/Slow Net?)")
    except httpx.ConnectError as e:
        print(f"{RED}CONNECTION ERROR{RESET} - Could not reach server. (DNS/Offline?)")
        print(f"  -> Detail: {e}")
    except httpx.SSLError as e:
        print(f"{RED}SSL ERROR{RESET} - Certificate verification failed.")
        print(f"  -> Detail: {e}")
    except Exception as e:
        print(f"{RED}ERROR{RESET} - {type(e).__name__}: {e}")
    return False

async def main():
    print("--- 🔍 ToxiScan Network Diagnostic Tool ---\n")
    
    # 1. Basic Internet Check
    internet = await test_connection("Google (Connectivity Check)", "https://www.google.com")
    if not internet:
        print("\n❌ CRITICAL: You seem to be offline or Google is blocked.")
        return

    print("\n--- API Checks ---")
    
    # 2. OpenFoodFacts
    await test_connection("OpenFoodFacts API", "https://world.openfoodfacts.org/api/v2/additive/e330")
    
    # 3. Wikipedia
    await test_connection("Wikipedia API", "https://en.wikipedia.org/api/rest_v1/page/summary/Citric_Acid")
    
    # 4. USDA
    usda_key = os.getenv("USDA_API_KEY", "DEMO_KEY") # Use env var or fake one just to test reachability
    usda_url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={usda_key}&query=apple"
    await test_connection("USDA API", usda_url)

    # 5. PubChem
    await test_connection("PubChem API", "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/cids/JSON")

    print("\n--- Diagnosis ---")
    print("If specific APIs failed but Google worked, your IP might be rate-limited or blocked.")
    print("If 'SSL ERROR' appeared, you need to update your python certificates.")
    print("If 'TIMEOUT' appeared, your network is too slow or a firewall is dropping packets.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
