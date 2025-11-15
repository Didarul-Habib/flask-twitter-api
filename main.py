import os

# ----------------------------------------------------
# ABSOLUTELY BLOCK ALL PROXY VARIABLES (Render injects hidden ones)
# ----------------------------------------------------
for p in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if p in os.environ:
        del os.environ[p]

# ALSO block httpx auto-detection
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"


import time
import re
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI


# ----------------------------------------------------
# Init Flask + OpenAI
# ----------------------------------------------------
app = Flask(__name__)
client = OpenAI()   # now safe — no proxies will be passed


# ----------------------------------------------------
# Keep-alive ping (Render free tier)
# ----------------------------------------------------
RENDER_URL = "https://crowntalk-v2-0.onrender.com"

def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL, timeout=6)
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()


# ----------------------------------------------------
# Tweet Text Fetcher
# ----------------------------------------------------
def get_tweet_text(url):
    try:
        clean = url.replace("https://", "").replace("http://", "")
        api = f"https://api.vxtwitter.com/{clean}"

        r = requests.get(api, timeout=10)
        d = r.json()

        if "tweet" in d and "text" in d["tweet"]:
            return d["tweet"]["text"]

        if "text" in d:
            return d["text"]

        return None
    except:
        return None


# ----------------------------------------------------
# AI Comment Generator (2 comments, retry)
# ----------------------------------------------------
def generate_comments(text):
    prompt = f"""
Generate two natural human comments based on this tweet.

Rules:
- 5–12 words each
- no emojis
- no hashtags
- no punctuation at end
- casual tone
- each comment in new line

Tweet:
{text}
"""

    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.65,
                max_tokens=60,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = r.choices[0].message.content.strip()
            lines = [x.strip() for x in raw.split("\n") if x.strip()]

            cleaned = []
            for c in lines:
                c = re.sub(r"[.,!?;:]+$", "", c)
                if 5 <= len(c.split()) <= 12:
                    cleaned.append(c)

            if len(cleaned) >= 2:
                return cleaned[:2]

        except Exception as e:
            print("AI attempt failed:", e)
            time.sleep(1.5)

    return ["generation failed", "please retry"]


# ----------------------------------------------------
# API Routes
# ----------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "CrownTALK backend online"})


@app.route("/comment", methods=["POST"])
def comment_api():
    body = request.json
    urls = body.get("urls", [])

    if not urls:
        return jsonify({"error": "No URLs"}), 400

    clean = []
    for u in urls:
        u = re.sub(r"\?.*$", "", u.strip())
        if u not in clean:
            clean.append(u)

    results = []
    failed = []

    for i in range(0, len(clean), 2):
        batch = clean[i:i+2]

        for url in batch:
            txt = get_tweet_text(url)
            if not txt:
                failed.append(url)
                continue

            comments = generate_comments(txt)
            results.append({"url": url, "comments": comments})

        time.sleep(2)

    return jsonify({"results": results, "failed": failed})


# ----------------------------------------------------
# Run Server
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
