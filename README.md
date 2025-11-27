# 🔬 ToxiScan: Multi-API Food Safety Aggregator

![Status](https://img.shields.io/badge/Status-Production_Ready-green)
![Stack](https://img.shields.io/badge/Tech-FastAPI_|_Tailwind_|_Nginx-blue)
![Deployment](https://img.shields.io/badge/Architecture-Load_Balanced_Cluster-orange)

**ToxiScan** is a distributed web application designed to analyze food additives (E-numbers) for toxicity, origin (Natural vs. Synthetic), and dosage limits. 

Unlike traditional apps that rely on static, local databases, ToxiScan functions as a **Real-Time Data Aggregator**. It queries multiple external APIs simultaneously, parses unstructured text using Natural Language Processing (Regex) techniques, and triangulates data to provide an instant safety profile.

---

## 📑 Table of Contents

1. [Project Overview & Objective](#-project-overview--objective)
2. [System Architecture](#-system-architecture)
3. [The "Smart" Aggregator Logic](#-the-smart-aggregator-logic)
4. [Technology Stack](#-technology-stack)
5. [Local Development Guide](#-local-development-guide)
6. [Production Deployment (3-Server Cluster)](#-production-deployment-3-server-cluster)
    - [Web Servers Configuration (Nginx + Gunicorn)](#1-web-servers-web-01--web-02)
    - [Load Balancer Configuration (HAProxy)](#2-load-balancer-lb-01)
7. [API Documentation](#-api-documentation)
8. [Authors & Credits](#-authors--credits)

---

## 🎯 Project Overview & Objective

The primary goal of ToxiScan is to solve the opacity of food labeling. While consumers see codes like "E102" or "E951", they rarely understand the biological implications.

**Key Features:**
* **Real-Time Analysis:** No mock data. Every search triggers live investigations.
* **Dosage Extraction:** Scans encyclopedic text to find "Acceptable Daily Intake" (ADI) limits in mg/kg.
* **Origin Detection:** Dynamically determines if an additive is **Natural** (Plant/Insect based) or **Synthetic** (Petroleum/Coal Tar based).
* **Autocomplete:** Instant suggestion engine based on the official OpenFoodFacts Taxonomy.
* **High Availability:** Deployed on a load-balanced architecture to ensure zero downtime.

---

## 🏗 System Architecture

ToxiScan uses a Microservices-style architecture deployed across three distinct servers.



**Data Flow:**
1.  **Client:** User types "Citric Acid" into the Frontend.
2.  **Load Balancer (HAProxy):** Receives traffic on Port 80 and routes it to the healthiest Web Server using a `RoundRobin` algorithm.
3.  **Web Server (Nginx):** Serves the static UI assets and Reverse Proxies API requests to the application server.
4.  **Application Server (Uvicorn/FastAPI):**
    * Queries **OpenFoodFacts API** for Identity & Risk Profile.
    * Queries **Wikipedia API** for detailed Description.
    * Runs **Regex Analysis** to merge and clean the data.
5.  **Response:** A unified JSON object is returned to the client.

---

## 🧠 The "Smart" Aggregator Logic

ToxiScan does not simply "lookup" data. It computes it.

### 1. The Multi-API Handshake
* **Step A (Identification):** The app first queries the **OpenFoodFacts Additive API**. This resolves "E330" to "Citric Acid" and retrieves the official EFSA (European Food Safety Authority) risk evaluation.
* **Step B (Context):** Using the resolved name, it queries the **Wikipedia Summary API**. This retrieves unstructured text describing the chemical.

### 2. Text Analysis Engine (Regex)
The backend uses Python's `re` module to perform keyword analysis on the fetched text:

* **Origin Detection:**
    * *Keywords:* "Petroleum", "Synthetic", "Coal Tar" $\rightarrow$ **Tag: Synthetic**.
    * *Keywords:* "Plant", "Extracted", "Fermentation" $\rightarrow$ **Tag: Natural**.
* **Dosage Extraction:**
    * The engine looks for patterns matching `ADI`, `LD50`, or `\d+ mg/kg`.
    * *Example:* Accessing text "...an ADI of 40 mg/kg was established..." extracts **"40 mg/kg"**.
* **Safety Fallback:**
    * If no specific dosage is found, the engine falls back to the EFSA evaluation (e.g., "No Risk" or "High Risk of Overexposure").

---

## 💻 Technology Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | HTML5, Vanilla JS | Lightweight, high-performance UI. |
| **Styling** | Tailwind CSS (CDN) | Responsive, modern design system. |
| **Backend** | Python 3.10+ | Core logic and data processing. |
| **Framework** | FastAPI | High-speed Async API framework. |
| **Network** | HTTPX | Asynchronous HTTP client for external API calls. |
| **Server** | Uvicorn / Gunicorn | ASGI Server for production performance. |
| **Proxy** | Nginx | Reverse Proxy and Static Asset Server. |
| **Balancing** | HAProxy | Layer 7 Load Balancer. |

---

## 🚀 Local Development Guide

Follow these steps to run ToxiScan on your local machine for testing.

**Prerequisites:** Python 3.8+, pip, git.

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/yourusername/toxiscan.git](https://github.com/yourusername/toxiscan.git)
    cd toxiscan
    ```

2.  **Create a Virtual Environment:**
    *(Required to avoid 'externally-managed-environment' errors)*
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Server:**
    ```bash
    python -m uvicorn main:app --reload
    ```

5.  **Access the App:**
    Open `http://127.0.0.1:8000` in your browser.

---

## 🌐 Production Deployment (3-Server Cluster)

This application is deployed on a custom infrastructure consisting of two web nodes and one load balancer.

### 1. Web Servers (`Web-01` & `Web-02`)
**IPs:** `34.207.191.228`, `52.90.221.65`

**Setup:**
* Files located in `/home/ubuntu/toxiscan`.
* **Systemd Service:** Keeps the app running in the background.
    * File: `/etc/systemd/system/toxiscan.service`
    * Command: `uvicorn main:app --host 0.0.0.0 --port 8000`
* **Nginx Configuration:**
    * Nginx listens on Port 80.
    * Serves static files (`index.html`) directly.
    * Proxies `/api/` traffic to `127.0.0.1:8000`.

**Nginx Config Block (`/etc/nginx/sites-available/toxiscan`):**
```nginx
server {
    listen 80;
    server_name _;

    location / {
        root /home/ubuntu/toxiscan;
        index index.html;
        try_files $uri $uri/ =404;
    }

    location /api/ {
        proxy_pass [http://127.0.0.1:8000](http://127.0.0.1:8000);
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
