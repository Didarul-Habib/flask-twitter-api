# ----------------------------------------------------
# FORCE CORRECT OPENAI VERSION ON RENDER
# ----------------------------------------------------
import os
os.system("pip uninstall -y openai > /dev/null 2>&1")
os.system("pip install openai==1.43.1 > /dev/null 2>&1")

# ----------------------------------------------------
# REMOVE RENDER PROXIES (fixes OpenAI proxy injection bug)
# ----------------------------------------------------
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
client = OpenAI()   # works correctly with 1.43.1


# ----------------------------------------------------
# KEEP RENDER AWAKE
# ----------------------------------------------------
def keep_awake():
    while True:
        try:
            requests.get("https://crowntalk-v2-0.onrender.com")
        except:
            pass
        time.sleep(300)  # ping every 5 min


threading.Thread(target=keep_awake, daemon=True).start()


# ----------------------------------------------------
# FETCH TWEET TEXT FROM VX TWITTER API
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
# GENERATE AI COMMENTS USING GPT-4O-MINI (1.43.1 COMPATIBLE)
# ----------------------------------------------------
def generate_comments(tweet_text):
    prompt = f"""
Generate two humanlike comments.
Rules:
- 5–12 words each
- no punctuation at end
- no emojis, no hashtags
- natural slang allowed (tbh, fr, ngl, btw, lowkey)
- comments must be different and based on the tweet
- exactly 2 lines, no labels

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

    # Clean URLs — remove duplicates and ? queries
    clean_urls = []
    for u in urls:
        u = u.strip()
        u = re.sub(r"\?.*$", "", u)
        if u not in clean_urls:
            clean_urls.append(u)

    results = []
    failed = []

    # BATCH SIZE = 2
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
