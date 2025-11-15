import os
import time
import re
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ----------------------------------------------------
# Flask + OpenAI
# ----------------------------------------------------
app = Flask(__name__)
client = OpenAI()

# ----------------------------------------------------
# Keep alive ping for Render free tier
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
# Fetch tweet content using VX API
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
# Generate AI comments (retry logic)
# ----------------------------------------------------
def generate_comments(text):
    prompt = f"""
Generate two humanlike comments based on this tweet.

Rules:
- 5–12 words each
- no emojis
- no hashtags
- no punctuation at end
- make them different and natural
- exactly two lines

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

            raw = r.choices[0].message.content.strip().split("\n")
            cleaned = []

            for c in raw:
                c = re.sub(r"[.,!?;:]+$", "", c.strip())
                if 5 <= len(c.split()) <= 12:
                    cleaned.append(c)

            if len(cleaned) >= 2:
                return cleaned[:2]

        except Exception as e:
            print("AI error:", e)
            time.sleep(1.5)

    return ["generation failed", "please retry"]

# ----------------------------------------------------
# Routes
# ----------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "CrownTALK backend running"})

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
# Run server
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
