// Relative path allows Nginx to proxy correctly
const API_BASE = "/api/v1"; 

const input = document.getElementById('search-input');
const list = document.getElementById('autocomplete-list');
const loader = document.getElementById('loader');
const card = document.getElementById('result-card');

let debounceTimer;

// --- AUTOCOMPLETE LOGIC ---
input.addEventListener('input', (e) => {
    const query = e.target.value;
    clearTimeout(debounceTimer);
    
    if (query.length < 2) {
        list.classList.add('hidden');
        return;
    }

    debounceTimer = setTimeout(async () => {
        try {
            const res = await fetch(`${API_BASE}/autocomplete?q=${encodeURIComponent(query)}`);
            const suggestions = await res.json();
            
            list.innerHTML = '';
            if (suggestions.length > 0) {
                suggestions.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    li.className = 'suggestion-item';
                    li.onclick = () => {
                        input.value = item;
                        list.classList.add('hidden');
                        handleSearch(item);
                    };
                    list.appendChild(li);
                });
                list.classList.remove('hidden');
            } else {
                list.classList.add('hidden');
            }
        } catch (err) {
            console.error("Autocomplete Error", err);
        }
    }, 300); // 300ms debounce
});

// Hide dropdown if clicked outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('#search-form')) {
        list.classList.add('hidden');
    }
});

// --- SEARCH LOGIC ---
document.getElementById('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    handleSearch(input.value);
    list.classList.add('hidden');
});

async function handleSearch(query) {
    if (!query) return;

    // UI Reset
    loader.classList.remove('hidden');
    card.classList.add('hidden');

    try {
        const res = await fetch(`${API_BASE}/search?query=${encodeURIComponent(query)}`);
        const data = await res.json();
        
        renderCard(data);
    } catch (err) {
        alert("Error analyzing additive. Please try again.");
    } finally {
        loader.classList.add('hidden');
    }
}

function renderCard(data) {
    // 1. Header Info
    document.getElementById('res-ename').textContent = data.eNumber || "Unknown";
    document.getElementById('res-name').textContent = data.name || "";
    
    // 2. Safety Badge
    const safetyEl = document.getElementById('res-safety');
    let safetyClass = "bg-gray-500";
    let safetyText = "Unknown Risk";

    if (data.safety === "safe") {
        safetyClass = "bg-green-500";
        safetyText = "Safe / Low Risk";
    } else if (data.safety === "caution") {
        safetyClass = "bg-yellow-500 text-black";
        safetyText = "Moderate Caution";
    } else if (data.safety === "high-risk") {
        safetyClass = "bg-red-600";
        safetyText = "High Risk";
    }
    
    safetyEl.className = `px-4 py-2 rounded-full font-bold uppercase text-sm tracking-wide text-white ${safetyClass}`;
    safetyEl.textContent = safetyText;

    // 3. Origin Badge
    const originEl = document.getElementById('res-origin');
    const isNatural = data.origin === "Natural";
    originEl.className = `px-3 py-1 rounded-md text-sm font-bold border ${isNatural ? 'bg-green-100 text-green-700 border-green-200' : 'bg-blue-100 text-blue-700 border-blue-200'}`;
    originEl.textContent = data.origin;

    // 4. Details
    document.getElementById('res-desc').textContent = data.description;
    document.getElementById('res-dosage').textContent = data.dosage;

    card.classList.remove('hidden');
}