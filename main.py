from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time

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
    return jsonify({"status": "✅ CrownTALK active and ready."})


# -------- COMMENT GENERATOR --------
@app.route("/comment", methods=["GET", "POST"])
def comment():
    urls = request.args.getlist("url") or (request.json.get("urls", []) if request.is_json else [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    if len(urls) > 5:
        return jsonify({"error": "Maximum 5 links allowed at once."}), 400

    # remove duplicates
    unique_urls = []
    duplicates = []
    for u in urls:
        if u not in unique_urls:
            unique_urls.append(u)
        else:
            duplicates.append(u)

    results = []
    for url in unique_urls:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        try:
            r = requests.get(api_url, timeout=10)
            data = r.json()
        except Exception as e:
            results.append({
                "url": url,
                "error": f"⚠️ Could not fetch tweet: {str(e)}"
            })
            continue

        if "text" not in data:
            results.append({
                "url": url,
                "error": "⚠️ Could not fetch this tweet (private/deleted)."
            })
            continue

        tweet_text = data["text"]
        author = data.get("user_screen_name", "unknown")

        # --- smarter prompt for realism and variation ---
        prompt = f"""
You are a social media user who writes natural, human-like comments — not robotic or repetitive.
Read the following tweet and create **two** unique, short, casual reactions.

Rules:
- Each comment must be 5–10 words.
- No emojis, hashtags, or punctuation except periods.
- Avoid starting comments with the same few words (like Love, Finally, This, Lowkey, etc).
- Avoid repeated tone or structure across comments.
- Use slang like "fr", "tbh", "ngl", "rn" naturally if it fits.
- Comments must sound like two different real people.
- Base both on the actual tweet context.

Tweet:
{tweet_text}

Give your answer in JSON like this:
{{"comments": ["comment one", "comment two"]}}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )

            raw_output = response.choices[0].message.content.strip()

            # Extract comments safely
            import json
            try:
                parsed = json.loads(raw_output)
                comments = parsed.get("comments", [])
            except Exception:
                # fallback if not valid JSON
                comments = [c.strip() for c in raw_output.split("\n") if c.strip()]

            results.append({
                "author": author,
                "url": url,
                "tweet_text": tweet_text,
                "comments": comments[:2]  # ensure only 2
            })

        except Exception as e:
            results.append({
                "url": url,
                "error": f"⚠️ GPT generation failed: {str(e)}"
            })

    return jsonify({
        "summary": f"Processed {len(results)} tweets.",
        "duplicates_ignored": duplicates,
        "results": results
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
