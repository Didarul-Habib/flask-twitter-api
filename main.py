import os
import time
import re
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()

# -------------------------
# Keep Render awake
# -------------------------
RENDER_URL = "https://crowntalk-v2-0.onrender.com"

def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL, timeout=6)
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------------
# Fetch tweet text (VX API)
# -------------------------
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

# -------------------------
# Generate comments
# -------------------------
def generate_comments(text):
    prompt = f"""
Generate two humanlike comments based on this tweet.

Rules:
- 5–12 words each
- no hashtags
- no emojis
- no punctuation
- different tone each
- exactly 2 lines output

Tweet:
{text}
"""

    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.65,
                max_tokens=70,
                messages=[{"role": "user", "content": prompt}],
            )

            out = resp.choices[0].message.content.strip().split("\n")

            cleaned = []
            for c in out:
                c = re.sub(r"[.,!?;:]+$", "", c)
                if 5 <= len(c.split()) <= 12:
                    cleaned.append(c)

            if len(cleaned) >= 2:
                return cleaned[:2]

        except Exception as e:
            print("AI error:", e)
            time.sleep(2)

    return ["generation failed", "retry later"]

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    return jsonify({"status": "CrownTALK backend OK"})

@app.route("/comment", methods=["POST"])
def comment_api():
    body = request.json or {}
    urls = body.get("urls", [])

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    clean = []
    for u in urls:
        u = u.strip()
        u = re.sub(r"\?.*$", "", u)
        if u not in clean:
            clean.append(u)

    results = []
    fails = []

    for i in range(0, len(clean), 2):
        batch = clean[i:i+2]

        for url in batch:
            txt = get_tweet_text(url)
            if not txt:
                fails.append(url)
                continue

            comments = generate_comments(txt)
            results.append({"url": url, "comments": comments})

        time.sleep(2)

    return jsonify({"results": results, "failed": fails})

# -------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
