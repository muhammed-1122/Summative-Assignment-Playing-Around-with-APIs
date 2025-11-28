# 🔬 ToxiScan: Multi-API Food Safety Aggregator

![Status](https://img.shields.io/badge/Status-Production_Ready-green)
![Stack](https://img.shields.io/badge/Tech-FastAPI_|_Tailwind_|_Nginx-blue)
![Deployment](https://img.shields.io/badge/Architecture-Load_Balanced_Cluster-orange)

**ToxiScan** is a distributed web application designed to analyze food additives (E-numbers) for toxicity, origin (Natural vs. Synthetic), and dosage limits.

Unlike simple lookup tools, ToxiScan functions as a **Real-Time Data Aggregator**. It queries multiple external APIs simultaneously, parses unstructured text using Natural Language Processing (Regex), and triangulates data to provide an instant safety profile.

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [System Architecture](#-system-architecture)
3. [Features & Logic](#-features--logic)
4. [Technology Stack](#-technology-stack)
5. [Local Development Guide](#-local-development-guide)
6. [Production Deployment](#-production-deployment-cluster-setup)
7. [Challenges & Lessons Learned](#-challenges--lessons-learned)
8. [Troubleshooting](#-troubleshooting)
9. [API Documentation & Credits](#-api-documentation--credits)

---

## 🎯 Project Overview

The primary goal of ToxiScan is to solve the opacity of food labeling. While consumers see codes like "E102" or "E951", they rarely understand the biological implications. This application bridges that gap by aggregating scientific data into a user-friendly dashboard.

**Core Value:**
* **Real-Time Analysis:** No mock data. Every search triggers live investigations across 4 global databases.
* **Smart Safety Logic:** Merges official EFSA risk profiles with keyword analysis of encyclopedic text.
* **High Availability:** Deployed on a load-balanced architecture to ensure reliability.

---

## 🏗 System Architecture

ToxiScan is deployed across a 3-server cluster using a **Microservices-style architecture**.

```mermaid
graph LR
    User[Client Browser] -- HTTP Request --> LB[Load Balancer (Nginx)]
    LB -- Round Robin --> Web1[Web-01 (Nginx + FastAPI)]
    LB -- Round Robin --> Web2[Web-02 (Nginx + FastAPI)]
    Web1 -- External APIs --> API[Internet]
    Web2 -- External APIs --> API[Internet]
```

## Data Flow
Client: User searches for "Citric Acid".

Load Balancer (Node Lb-01): Nginx receives the traffic and routes it to the least busy server using a Round Robin upstream configuration.

Web Server (Nodes Web-01/02): Nginx acts as a Reverse Proxy, forwarding port 80 traffic to the internal Uvicorn application running on port 8000.

Application Layer: FastAPI performs parallel async requests to external APIs and computes the result.

---

## 🧠 Features & Logic
### 1. The Multi-API Handshake
ToxiScan does not rely on a single source of truth. It triangulates data:

Identification: Queries OpenFoodFacts to resolve "E330" to "Citric Acid".

Context: Queries Wikipedia for unstructured description text.

Verification: Queries USDA to check if the item is a recognized food source.

Structure: Queries PubChem for molecular imagery.

---

### 2. Hybrid Safety Analysis
The backend uses a fallback system to determine safety:

Hardcoded Safety Net: Checks against a curated list of known high-risk additives (e.g., Nitrites, Aspartame).

API Risk Profile: Checks EFSA data from OpenFoodFacts.

NLP Keyword Scanning: If the above fail, it scans the description text for keywords like "Carcinogen," "Banned," or "Synthetic."

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

    location /api/ {}
```

---

🌐 Production Deployment (Cluster Setup)
The application is hosted on three AWS servers. Below is the configuration used to achieve High Availability.

1. Web Servers (Web-01 & Web-02)
IPs: 34.207.191.228, 52.90.221.65

Role: Serve the application.

Nginx Configuration (/etc/nginx/sites-available/toxiscan): We use Nginx as a reverse proxy to forward port 80 traffic to the internal Uvicorn server.
```server {
    listen 80;
    server_name _;

    location / {
        proxy_pass [http://127.0.0.1:8000](http://127.0.0.1:8000);
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
2. Load Balancer (Lb-01)
IP: 18.207.173.143

Role: Distribute traffic.

Nginx Load Balancer Config: An upstream block is defined to cycle requests between the two web servers.
```upstream toxiscan_backend {
    server 34.207.191.228; # Web-01
    server 52.90.221.65;   # Web-02
}

server {
    listen 80;
    location / {
        proxy_pass http://toxiscan_backend;
    }
}
```
---

## 💡 Challenges & Lessons Learned

### 1. API Input Formatting Issues
When I first tested the application, it kept failing to fetch data from Wikipedia and PubChem. At first, I thought it was a network connection problem or a firewall blocking the requests. However, after troubleshooting, I realized the issue was actually with the text I was sending. The APIs expected specific formatting (like "Citric_Acid"), but my application was sending raw text (like "E330 - Citric Acid"). I fixed this by writing a simple script to clean and format the text before sending it out.

### 2. Deployment Directory Configuration
Deploying the application to the AWS servers was difficult. I initially got a "502 Bad Gateway" error because the server couldn't find my main.py file. It turned out that my code on GitHub was inside a subfolder, but my server configuration was looking for it in the main folder. Instead of deleting and re-uploading my repository, I learned how to configure the server settings (Systemd) to point specifically to that subfolder using the WorkingDirectory directive.

### 3. Server Resource Limits
Once the application was running, it would crash after about a minute. I discovered that loading the large list of food additives was using up all the RAM on the small server. I overcame this by adding "Swap Memory," which allows the server to use a portion of the hard drive as extra memory when it runs out of RAM.

### 4. Incomplete API Data
I noticed that the main API I was using often returned empty results for safety information, which made the app say "Safe" even for additives that might be dangerous. To fix this, I created a backup system. If the API returns nothing, my code now checks a manual list of known dangerous additives and scans the description text for warning words to ensure the user still gets a result.

### 5. Python Environment Management
I had trouble installing the necessary libraries on the server because of conflicts with the system's built-in Python version. I learned that I needed to create a "Virtual Environment" to keep my project's libraries separate from the rest of the system, which solved the installation errors.

---
## 🛠 Troubleshooting
The repository includes a network diagnostic tool (debug_network.py) to help identify connectivity issues with the external APIs.

How to use:

python3
```debug_network.py```

* **This script runs a health check on:**
    *  OpenFoodFacts API Endpoint
    *  OpenFoodFacts API Endpoint
    *  Wikipedia API Endpoint
    *  USDA API Endpoint
    *  PubChem API Endpoint

---

## 📚 API Documentation & Credits

This project would not be possible without the following open-source data providers:

OpenFoodFacts API: Used for additive taxonomy and initial risk assessment.

Wikipedia REST API: Used for retrieving descriptive summaries of chemical compounds.

USDA FoodData Central: Used to verify if an additive is a recognized food source.

PubChem API: Used to generate molecular structure imagery.
