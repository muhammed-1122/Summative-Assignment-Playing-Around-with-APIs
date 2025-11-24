import re
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- IN-MEMORY DATABASE FOR AUTOCOMPLETE ---
additive_index: List[str] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global additive_index
    taxonomy_url = "https://world.openfoodfacts.org/data/taxonomies/additives.json"
    logger.info("Fetching Additive Taxonomy for Autocomplete...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(taxonomy_url)
            if resp.status_code == 200:
                data = resp.json()
                temp_list = []
                for key, value in data.items():
                    if 'name' in value and 'en' in value['name']:
                        e_code = key.split(':')[-1].upper()
                        name = value['name']['en']
                        temp_list.append(f"{e_code} - {name}")
                
                additive_index = sorted(temp_list)
                logger.info(f"Loaded {len(additive_index)} additives into memory.")
            else:
                logger.error("Failed to load taxonomy.")
        except Exception as e:
            logger.error(f"Startup Error: {e}")
            
    yield
    additive_index.clear()

app = FastAPI(title="ToxiScan API", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER FUNCTIONS ---

def extract_origin(text: str) -> str:
    text_lower = text.lower()
    synthetic_keywords = ["synthetic", "artificial", "manufactured", "petroleum", "chemical synthesis", "derived from coal"]
    natural_keywords = ["natural", "extracted from", "plant", "animal", "insect", "fermentation", "found in"]
    
    # Priority check
    for word in synthetic_keywords:
        if word in text_lower:
            return "Synthetic"
    for word in natural_keywords:
        if word in text_lower:
            return "Natural"
    return "Unknown"

def extract_dosage(text: str) -> str:
    # Look for "ADI", "Acceptable Daily Intake", or number patterns like "40 mg/kg"
    regex_pattern = r"([^.]*?(?:ADI|acceptable daily intake|mg\/kg)[^.]*\.)"
    match = re.search(regex_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "No specific dosage limit found in summary."

# --- ROUTES ---

@app.get("/api/v1/autocomplete")
async def autocomplete(q: str = Query(..., min_length=1)):
    q_clean = q.lower()
    # Simple search: checks if query is inside the string
    matches = [item for item in additive_index if q_clean in item.lower()]
    return matches[:5]

@app.get("/api/v1/search")
async def search_additive(query: str):
    # If user selects "E330 - Citric Acid", we split it.
    # If user types "E330", we keep it.
    clean_query = query.split("-")[0].strip().lower()
    
    result = {
        "eNumber": clean_query.upper(),
        "name": "Unknown",
        "safety": "unknown",
        "origin": "Unknown",
        "dosage": "Data unavailable",
        "description": "No description available."
    }

    # IMPORTANT: Wikipedia blocks requests without a User-Agent!
    headers = {
        "User-Agent": "ToxiScanStudentProject/1.0 (contact@example.com)"
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        
        # STEP A: OpenFoodFacts
        try:
            # We assume input is an E-number (e.g., e330). OFF requires 'e' prefix usually.
            if not clean_query.startswith('e') and clean_query.isdigit():
                search_query = f"e{clean_query}"
            else:
                search_query = clean_query

            off_url = f"https://world.openfoodfacts.org/api/v2/additive/{search_query}"
            logger.info(f"Querying OFF: {off_url}")
            
            off_resp = await client.get(off_url)
            
            if off_resp.status_code == 200:
                off_data = off_resp.json()
                
                # Try to get Name
                if 'name' in off_data and 'en' in off_data['name']:
                     result['name'] = off_data['name']['en']
                
                # Try to get Wiki Data ID (helps confirm it exists)
                if 'wikidata' in off_data:
                    result['safety'] = "safe" # Default if valid additive found
                    
                # Advanced: Check for "Overexposure Risk" field in OFF
                if 'topics' in off_data:
                    topics = str(off_data['topics']).lower()
                    if 'risk' in topics or 'alert' in topics:
                        result['safety'] = "caution"

        except Exception as e:
            logger.error(f"OFF API Error: {e}")

        # STEP B: Wikipedia
        # If OFF failed to find a name, we can't search Wiki easily.
        # Fallback: if result['name'] is still "Unknown", try searching Wiki with the E-number directly? 
        # Usually better to search with the Name if OFF gave us one.
        
        search_term = result['name'] if result['name'] != "Unknown" else clean_query
        
        try:
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_term}"
            logger.info(f"Querying Wiki: {wiki_url}")
            
            wiki_resp = await client.get(wiki_url)
            
            if wiki_resp.status_code == 200:
                wiki_data = wiki_resp.json()
                if 'extract' in wiki_data:
                    full_text = wiki_data['extract']
                    result['description'] = full_text
                    result['origin'] = extract_origin(full_text)
                    result['dosage'] = extract_dosage(full_text)
                    
                    # Refine Safety based on text analysis
                    lower_text = full_text.lower()
                    if "carcinogen" in lower_text or "banned" in lower_text or "cancer" in lower_text:
                        result['safety'] = "high-risk"
                    elif "allergic" in lower_text or "hyperactivity" in lower_text or "asthma" in lower_text:
                         if result['safety'] != "high-risk":
                            result['safety'] = "caution"
                    elif result['safety'] == "unknown":
                        result['safety'] = "safe" # If found in wiki but no scary words, assume safe
            else:
                logger.warning(f"Wiki returned status {wiki_resp.status_code}")

        except Exception as e:
            logger.error(f"Wiki API Error: {e}")

    return result

# ==========================================
# LOCAL SERVING LOGIC (KEEP THIS FOR TESTING)
# ==========================================
@app.get("/")
async def read_root():
    if os.path.exists('index.html'):
        return FileResponse('index.html')
    return {"error": "index.html not found"}

@app.get("/{filename}")
async def serve_static(filename: str):
    allowed = {".html", ".css", ".js", ".png", ".ico"}
    _, ext = os.path.splitext(filename)
    if ext in allowed and os.path.exists(filename):
        return FileResponse(filename)
    return {"error": "File not found"}