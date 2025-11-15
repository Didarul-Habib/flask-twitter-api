# ----------------------------------------------------
# HARD-LOCK OPENAI VERSION (Render-proof)
# ----------------------------------------------------
import os
import subprocess

# Delete wrong version if Render installs it
subprocess.run("pip uninstall -y openai", shell=True)
subprocess.run("pip install openai==1.43.1", shell=True)

# Remove Render global proxy variables (fixes Client(proxies) bug)
for p in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if p in os.environ:
        del os.environ[p]

# ----------------------------------------------------
# IMPORTS
# ----------------------------------------------------
import time
import re
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI


# ----------------------------------------------------
# INIT
# ----------------------------------------------------
app = Flask(__name__)
client = OpenAI()  # now 100% safe


# ----------------------------------------------------
# KEEP RENDER AWAKE
# ----------------------------------------------------
def keep_awake():
    while True:
        try:
            requests.get("https://crowntalk-v2-0.onrender.com")
        except:
            pass
        time.sleep(300)


threading.Thread(target=keep_awake, daemon=True).start()


# ----------------------------------------------------
# FETCH TWEET TEXT
# ----------------------------------------------------
def get_tweet_text(url):
    try:
        clean = url.replace("https://", "").replace("http://", "")
        api = f"https://api.vxtwitter.com/{clean}"

        r = requests.get(api, timeout=10)
        data = r.json()

        if "tweet" in data and "text" in data["tweet"]:
            return data["tweet"]["text"]

        return None
    except:
        return None


# ----------------------------------------------------
# AI COMMENT GENERATOR
# ----------------------------------------------------
def generate_comments(tweet_text):
    prompt = f"""
Generate two humanlike comments.
Rules:
- 5–12 words each
- no punctuation at end
- no emojis
- no hashtags
- natural slang allowed (tbh, fr, ngl, lowkey)
- comments must be different
- based on tweet
- exactly 2 lines

Tweet:
{tweet_text}
"""

    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.65,
                max_tokens=60,
                messages=[{"role": "user", "content": prompt}],
            )

            out = resp.choices[0].message.content.strip().split("\n")
            out = [re.sub(r"[.,!?;:]+$", "", c).strip() for c in out]
            out = [c for c in out if 5 <= len(c.split()) <= 12]

            if len(out) >= 2:
                return out[:2]

        except Exception as e:
            print("AI error:", e)
            time.sleep(2)

    return ["generation failed", "please retry"]


# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "CrownTALK backend running"})


@app.route("/comment", methods=["POST"])
def comment_api():
    body = request.json
    urls = body.get("urls", [])

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    clean_urls = []
    for u in urls:
        u = u.strip()
        u = re.sub(r"\?.*$", "", u)
        if u not in clean_urls:
            clean_urls.append(u)

    results = []
    failed = []

    for i in range(0, len(clean_urls), 2):
        batch = clean_urls[i:i + 2]

        for url in batch:
            txt = get_tweet_text(url)
            if not txt:
                failed.append(url)
                continue

            comments = generate_comments(txt)

            results.append({
                "url": url,
                "comments": comments,
            })

        time.sleep(3)

    return jsonify({
        "results": results,
        "failed": failed
    })


# ----------------------------------------------------
# RUN
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
