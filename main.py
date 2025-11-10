from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, re

app = Flask(__name__)
client = OpenAI()

# -------- KEEP SERVER AWAKE --------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/")
            print("Ping sent to keep server awake.")
        except Exception as e:
            print("Ping failed:", e)
        time.sleep(10 * 60)  # every 10 minutes

threading.Thread(target=keep_alive, daemon=True).start()

# -------- HOME ROUTE --------
@app.route("/")
def home():
    return "✅ Server active and ready."

# -------- COMMENT GENERATOR (Batch Mode + URL Cleanup) --------
@app.route("/comment", methods=["GET", "POST"])
def comment():
    # accept ?url=...&url=... OR JSON body { "urls": [...] }
    urls = request.args.getlist("url") or (request.json.get("urls", []) if request.is_json else [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    if len(urls) > 5:
        return jsonify({"error": "Maximum 5 links allowed at once."}), 400

    # remove duplicates and clean URLs
    unique_urls, duplicates = [], []
    for u in urls:
        clean_url = re.sub(r'\?.*', '', u.strip())  # remove query params
        if clean_url not in unique_urls:
            unique_urls.append(clean_url)
        else:
            duplicates.append(clean_url)

    # fetch tweet texts
    tweet_data = []
    for url in unique_urls:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        try:
            r = requests.get(api_url, timeout=10)
            data = r.json()
            if "text" in data:
                tweet_data.append({
                    "url": url,
                    "author": data.get("user_screen_name", "unknown"),
                    "tweet_text": data["text"]
                })
            else:
                tweet_data.append({
                    "url": url,
                    "error": "⚠️ Could not fetch this tweet (private or deleted)."
                })
        except Exception as e:
            tweet_data.append({"url": url, "error": f"⚠️ Fetch failed: {e}"})

    # build one GPT prompt for all fetched tweets
    prompt = (
        "Write two short comments (5–10 words each, no emojis, no punctuation).\n"
        "Each pair must be relevant to its tweet content.\n"
        "Label each clearly as: Tweet 1:, Tweet 2:, etc.\n\n"
    )

    valid_tweets = [t for t in tweet_data if "tweet_text" in t]
    for i, t in enumerate(valid_tweets, 1):
        prompt += f"Tweet {i}: {t['tweet_text']}\n"

    if not valid_tweets:
        return jsonify({"error": "None of the tweets could be fetched."}), 400

    # one GPT call for all tweets
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        gpt_output = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": f"GPT request failed: {e}"}), 500

    # format clean output
    formatted_output = ""
    for i, t in enumerate(tweet_data, start=1):
        formatted_output += f"🔗 {t['url']}\n"
        if "error" in t:
            formatted_output += f"{t['error']}\n"
        else:
            section = f"Tweet {i}:"
            next_section = f"Tweet {i+1}:"
            start = gpt_output.find(section)
            end = gpt_output.find(next_section) if next_section in gpt_output else len(gpt_output)
            comment_block = gpt_output[start:end].replace(section, "").strip() if start != -1 else "(no comment found)"
            formatted_output += f"{comment_block}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(tweet_data)} tweets.",
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
