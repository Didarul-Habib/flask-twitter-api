from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, json

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
        time.sleep(10 * 60)

threading.Thread(target=keep_alive, daemon=True).start()


@app.route("/")
def home():
    return jsonify({"status": "✅ CrownTALK active and ready."})


@app.route("/comment", methods=["GET", "POST"])
def comment():
    urls = request.args.getlist("url") or (request.json.get("urls", []) if request.is_json else [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400
    if len(urls) > 5:
        return jsonify({"error": "Maximum 5 links allowed at once."}), 400

    unique_urls, duplicates, results = [], [], []
    for u in urls:
        if u not in unique_urls:
            unique_urls.append(u)
        else:
            duplicates.append(u)

    for url in unique_urls:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        try:
            r = requests.get(api_url, timeout=10)
            data = r.json()
        except Exception as e:
            results.append({"url": url, "error": f"⚠️ Could not fetch tweet: {str(e)}"})
            continue

        if "text" not in data:
            results.append({"url": url, "error": "⚠️ Could not fetch this tweet (private/deleted)."})
            continue

        tweet_text = data["text"]
        author = data.get("user_screen_name", "unknown")

        # --- smarter prompt ---
        prompt = f"""
You are a social media user who writes human-like comments. 
Create two short, natural, unique reactions for this tweet.

Rules:
- 5–10 words per comment.
- No emojis, hashtags, or punctuation except periods.
- Avoid repetitive patterns or starting words.
- Use light slang (tbh, fr, rn, ngl) only if it fits.
- Each comment must sound from a different person.
- Base both comments on the actual tweet content.

Tweet:
{tweet_text}

Respond ONLY in JSON as:
{{"comments": ["first", "second"]}}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )
            raw_output = response.choices[0].message.content.strip()
            try:
                parsed = json.loads(raw_output)
                comments = parsed.get("comments", [])
            except Exception:
                comments = [c.strip() for c in raw_output.split("\n") if c.strip()]

            comment_items = [{"text": c, "copy_text": c} for c in comments[:2]]

            results.append({
                "author": author,
                "url": url,
                "tweet_text": tweet_text,
                "comments": comment_items
            })

        except Exception as e:
            results.append({"url": url, "error": f"⚠️ GPT generation failed: {str(e)}"})

    return jsonify({
        "summary": f"Processed {len(results)} tweets.",
        "duplicates_ignored": duplicates,
        "results": results
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
