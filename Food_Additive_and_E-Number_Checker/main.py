import os
import re
import asyncio
import logging
import traceback
import urllib.parse
from contextlib import asynccontextmanager
from typing import List, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import httpx

load_dotenv()

# --- Configuration ---
USDA_API_KEY = os.getenv("USDA_API_KEY")
USDA_ENDPOINT = "https://api.nal.usda.gov/fdc/v1/foods/search"
OFF_TAXONOMY_URL = "https://static.openfoodfacts.org/data/taxonomies/additives.json"
OFF_ADDITIVE_URL = "https://world.openfoodfacts.org/api/v2/additive"
OFF_SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"
WIKI_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
PUBCHEM_CID_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/cids/JSON"
PUBCHEM_IMG_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/PNG?record_type=2d&image_size=300x300"

API_HEADERS = {"User-Agent": "ToxiScan-StudentProject/1.0"}

# --- Hybrid Safety Logic: Hardcoded Overrides ---
KNOWN_RISKS = {
    # High Risk / Avoid
    "e250": "high", "e251": "high", "e249": "high", "e252": "high", # Nitrites/Nitrates
    "e621": "moderate", # MSG
    "e951": "moderate", "e950": "moderate", # Aspartame/Acesulfame K
    "e102": "moderate", "e129": "moderate", "e133": "moderate", # Artificial Colors
    "e171": "high", # Titanium Dioxide (Banned in EU)
    "e220": "moderate", # Sulfur dioxide
    "e211": "moderate", # Sodium benzoate
    "e320": "high", "e321": "high", # BHA / BHT
    "e924": "high" # Potassium bromate
}

# --- Global Storage ---
additive_taxonomy: Dict[str, str] = {}
taxonomy_list: List[str] = []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ToxiScan")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load taxonomy on startup."""
    async with httpx.AsyncClient(headers=API_HEADERS, timeout=15.0) as client:
        try:
            logger.info("⏳ Loading Additive Taxonomy...")
            resp = await client.get(OFF_TAXONOMY_URL)
            if resp.status_code == 200:
                data = resp.json()
                for key, value in data.items():
                    code = key.split(':')[-1].lower()
                    additive_taxonomy[code] = code
                    taxonomy_list.append(code)
                    
                    names = value.get('name', {})
                    if 'en' in names:
                        name_lower = names['en'].lower()
                        additive_taxonomy[name_lower] = code
                        taxonomy_list.append(names['en'])
                logger.info(f"✅ Taxonomy Loaded: {len(taxonomy_list)} entries ready.")
            else:
                logger.warning(f"⚠️ Taxonomy failed to load. Status: {resp.status_code}")
        except Exception as e:
            logger.error(f"❌ Taxonomy Error: {e}")
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=".")

# --- Helper Logic ---
def analyze_safety(data: dict, code: str, description: str) -> dict:
    """
    Determines safety using 3 checks:
    1. Hardcoded 'Known Bad' list.
    2. API Data (if available).
    3. Keyword scan of the Wikipedia description.
    """
    risk_level = "low" # Default
    
    # Check 1: Hardcoded List (Most Reliable)
    if code and code in KNOWN_RISKS:
        risk_level = KNOWN_RISKS[code]

    # Check 2: API Data (OpenFoodFacts)
    elif data:
        api_risk = data.get("overexposure_risk", {}).get("risk")
        if api_risk:
            risk_level = api_risk

    # Check 3: Text Analysis (Fallback)
    # If we still think it's low, scan the text for danger words
    if risk_level == "low" and description:
        text = description.lower()
        high_keywords = ["carcinogen", "cancer", "banned", "toxic", "DNA damage"]
        mod_keywords = ["hyperactivity", "allergy", "asthma", "migraine", "intolerance", "children"]
        
        if any(k in text for k in high_keywords):
            risk_level = "high"
        elif any(k in text for k in mod_keywords):
            risk_level = "moderate"

    # --- Return the correct badge ---
    if risk_level == "high":
        return {"label": "High Risk / Avoid", "color": "bg-red-600 text-white", "icon": "⚠️"}
    elif risk_level == "moderate":
        return {"label": "Moderate Caution", "color": "bg-yellow-500 text-black", "icon": "✋"}
    else:
        return {"label": "Safe / Low Risk", "color": "bg-emerald-600 text-white", "icon": "✅"}

def analyze_origin(summary: str) -> str:
    if not summary: return "Origin Unknown"
    text = summary.lower()
    synthetic = ["petroleum", "artificial", "synthetic", "lab", "chemical synthesis", "coal tar", "preservative"]
    natural = ["plant", "extracted", "natural", "fruit", "vegetable", "fermentation", "animal", "vitamin", "mineral"]
    
    if any(k in text for k in synthetic): return "Synthetic / Artificial"
    if any(k in text for k in natural): return "Natural Origin"
    return "Origin Unknown"

# --- Fetchers ---
async def fetch_off_data(client, code):
    try:
        if not code: return None
        # Ensure code is clean (e.g. e330)
        clean_code = code.split(' ')[0] 
        resp = await client.get(f"{OFF_ADDITIVE_URL}/{clean_code}")
        return resp.json() if resp.status_code == 200 else None
    except: return None

async def fetch_wiki_data(client, name):
    try:
        if not name: return None
        # CLEANUP: "E330 - Citric Acid" -> "Citric_Acid"
        # 1. Remove E-code prefix if present
        name = re.sub(r'^[eE]\d+\s*[-–]\s*', '', name)
        
        # 2. Format for Wiki (Title Case, Underscores)
        clean = name.strip().title().replace(" ", "_")
        
        url = f"{WIKI_API_URL}/{clean}"
        resp = await client.get(url)
        return resp.json() if resp.status_code == 200 else None
    except: return None

async def fetch_usda(client, name):
    if not USDA_API_KEY or not name: return False
    try:
        # Cleanup name for USDA search as well
        clean_name = re.sub(r'^[eE]\d+\s*[-–]\s*', '', name)
        params = {"api_key": USDA_API_KEY, "query": clean_name, "dataType": ["Foundation", "SR Legacy"], "pageSize": 1}
        resp = await client.get(USDA_ENDPOINT, params=params)
        if resp.status_code == 200:
            d = resp.json()
            if d.get("totalHits", 0) > 0:
                food_name = d["foods"][0]["description"].lower()
                return clean_name.lower() in food_name
    except: pass
    return False

async def fetch_products(client, code, name):
    try:
        q = code if code else name
        if not q: return []
        params = {"additives_tags": q, "page_size": 3, "fields": "product_name,image_front_small_url"}
        resp = await client.get(OFF_SEARCH_URL, params=params)
        return resp.json().get("products", []) if resp.status_code == 200 else []
    except: return []

async def fetch_pubchem_cid(client, name):
    try:
        if not name: return None
        # Remove E-code junk before asking PubChem
        clean_name = re.sub(r'^[eE]\d+\s*[-–]\s*', '', name).strip()
        
        encoded_name = urllib.parse.quote(clean_name)
        url = PUBCHEM_CID_URL.format(encoded_name)
        
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            cids = data.get("IdentifierList", {}).get("CID", [])
            if cids: return cids[0]
    except: pass
    return None

# --- Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/autocomplete")
async def autocomplete(q: str):
    q_lower = q.lower()
    matches = [x for x in taxonomy_list if q_lower in x.lower()]
    return matches[:10]

@app.get("/api/analyze/{query}")
async def analyze_endpoint(query: str):
    try:
        query_clean = query.lower().strip()
        
        # --- INPUT CLEANING STEP ---
        # If input is "E330 - Citric Acid", split it.
        # Regex looks for: Starts with E+digits, then separator, then Name
        match = re.match(r"^([e]\d+)\s*[-–_]\s*(.+)$", query_clean)
        
        if match:
            e_code = match.group(1) # e330
            search_name = match.group(2) # citric acid
        else:
            # Standard lookup
            e_code = additive_taxonomy.get(query_clean)
            if not e_code and query_clean.startswith('e') and any(c.isdigit() for c in query_clean):
                 e_code = query_clean
            search_name = query_clean

        logger.info(f"Parsed -> Code: {e_code}, Name: {search_name}")

        async with httpx.AsyncClient(headers=API_HEADERS, timeout=20.0) as client:
            
            # 1. Identity (Use Code)
            off_data = await fetch_off_data(client, e_code)
            
            # 2. Resolve Canonical Name
            # If OFF gave us a good name, prefer it. Otherwise use our cleaned search_name.
            canonical_name = search_name
            if off_data:
                names = off_data.get("display_name_translations", {})
                canonical_name = names.get("en", names.get("fr", search_name))
            
            logger.info(f"Canonical Name for API Search: {canonical_name}")

            # 3. Parallel Fetch (Use Name)
            wiki_task = fetch_wiki_data(client, canonical_name)
            usda_task = fetch_usda(client, canonical_name)
            prod_task = fetch_products(client, e_code, canonical_name)
            cid_task = fetch_pubchem_cid(client, canonical_name)
            
            wiki_data, usda_verified, products, pubchem_cid = await asyncio.gather(
                wiki_task, usda_task, prod_task, cid_task
            )

        # --- Aggregate ---
        
        description = "Description unavailable."
        if wiki_data:
            description = wiki_data.get("extract", "Description unavailable.")

        # FIXED: Passing all 3 arguments (Data, Code, Description)
        safety = analyze_safety(off_data, e_code, description)
        
        origin = analyze_origin(description)
        
        # Image Logic
        img_url = ""
        if pubchem_cid:
            img_url = PUBCHEM_IMG_URL.format(pubchem_cid)
        else:
            # Last resort fallback
            safe_name = urllib.parse.quote(canonical_name)
            img_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{safe_name}/PNG?record_type=2d&image_size=300x300"

        return JSONResponse({
            "identity": {
                "name": canonical_name.title(),
                "code": e_code.upper() if e_code else "Unknown"
            },
            "safety": safety,
            "origin": origin,
            "description": description,
            "usda_verified": usda_verified,
            "structure_image": img_url,
            "products": products
        })

    except Exception as e:
        error_msg = traceback.format_exc()
        logger.error(f"❌ BACKEND ERROR:\n{error_msg}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
