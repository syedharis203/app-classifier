
from flask import Flask, request, jsonify
import logging
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import google.generativeai as genai
import os

# Load API key from env variable or fallback
GENAI_KEY = os.environ.get("GENAI_API_KEY", "AIzaSyCpXOTRkqAiOgBi8MVkedeQd-6BbFd6UJU")
genai.configure(api_key=GENAI_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash-exp")

app = Flask(__name__)

@app.route("/classify", methods=["POST"])
def classify():
    data = request.json
    app_link = data.get("url", "")
    result = classify_url_or_app(app_link)
    return result
risky_terms = ["malware", "phishing", "virus", "trojan", "unofficial", ".apk", "bet", "rummy", "lottery", "fantasy", "dream11"]
explicit_terms = ["porn", "adult", "sex", "xxx", "erotic"]

def scrape_play_store(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        name = soup.find("h1").text if soup.find("h1") else "Unknown"
        desc = soup.find("meta", attrs={"name": "description"})
        return name, desc["content"] if desc else "No description"
    except Exception as e:
        logging.warning(f"Play Store scrape failed: {e}")
        return "Unknown", "No description"

def scrape_app_store(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        name = soup.find("h1").text if soup.find("h1") else "Unknown"
        description = soup.find("meta", attrs={"name": "description"})
        return name, description["content"] if description else "No description"
    except Exception as e:
        logging.warning(f"App Store scrape failed: {e}")
        return "Unknown", "No description"

def classify_url_or_app(app_link):
    parsed = urlparse(app_link)
    platform = "Unknown"
    app_identifier = app_link.split('/')[-1]

    if "play.google.com" in app_link:
        platform = "Google Play Store"
        if "id=" in app_link:
            app_identifier = parse_qs(parsed.query).get("id", ["Unknown"])[0]
        name, description = scrape_play_store(app_link)

    elif "apps.apple.com" in app_link:
        platform = "Apple App Store"
        app_identifier = app_link.split("/")[-1]
        name, description = scrape_app_store(app_link)

    else:
        name = "Unknown"
        description = "No description"

    lower_url = app_link.lower()

    if any(term in lower_url for term in explicit_terms):
        return {
            "platform": platform,
            "app_identifier": app_identifier,
            "category": "Explicit Content",
            "risk_level": "Very High",
            "spam_status": "True"
        }

    if any(term in lower_url for term in risky_terms):
        cat = "Gambling" if any(g in lower_url for g in ["rummy", "dream11", "fantasy", "bet", "lottery"]) else "Malicious"
        return {
            "platform": platform,
            "app_identifier": app_identifier,
            "category": cat,
            "risk_level": "Very High",
            "spam_status": "True"
        }

    prompt = f"""
You are a cybersecurity and content classification AI.

Given the following mobile app info, return a classification JSON.

App Link: {app_link}
App Name: {name}
App Description: {description}

Return this format:
{{
  "platform": "...",
  "app_identifier": "...",
  "category": "...",
  "risk_level": "...",
  "spam_status": "..."
}}
"""

    try:
        result = model.generate_content(prompt)
        return json.loads(result.text)
    except Exception as e:
        logging.error(f"Gemini AI error: {e}")
        return {
            "platform": platform,
            "app_identifier": app_identifier,
            "category": "Unknown",
            "risk_level": "Unknown",
            "spam_status": "Unknown"
        }

@app.route('/classify', methods=['POST'])
def classify():
    data = request.json
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    result = classify_url_or_app(url)
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return "🛡️ App Classification API is running!", 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
