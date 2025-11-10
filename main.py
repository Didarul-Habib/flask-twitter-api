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
    return "✅ Server active and ready."

# -------- COMMENT GENERATOR --------
@app.route("/comment", methods=["GET", "POST"])   # <--- accepts both
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
        r = requests.get(api_url)
        data = r.json()

        if "text" not in data:
            results.append({
                "url": url,
                "error": "⚠️ Could not fetch this tweet (private/deleted)."
            })
            continue

        tweet_text = data["text"]
        author = data.get("user_screen_name", "unknown")

        prompt = (
            f"Write two short comments between 4 and 8 words reacting to this tweet:\n"
            f"{tweet_text}\n"
            f"One casual and one smart influencer style."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )

        comments = response.choices[0].message.content
        results.append({
            "author": author,
            "url": url,
            "tweet_text": tweet_text,
            "comments": comments
        })

    # -------- CLEAN TEXT OUTPUT --------
    formatted_output = ""
    for i, r in enumerate(results, start=1):
        formatted_output += f"🔗 {r['url']}\n"
        if "error" in r:
            formatted_output += f"{r['error']}\n"
        else:
            formatted_output += f"{r['comments']}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} tweets.",
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
