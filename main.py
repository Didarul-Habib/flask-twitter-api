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
        clean_url = u.split("?")[0]
        if clean_url not in unique_urls:
            unique_urls.append(clean_url)
        else:
            duplicates.append(clean_url)

    results = []
    for url in unique_urls:
        try:
            start_time = time.time()
            api_url = f"https://api.vxtwitter.com/{url.replace('https://', '').replace('http://', '')}"
            r = requests.get(api_url, timeout=15)
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
                "For the following tweet, write two unique, human-sounding comments (5–10 words each).\n"
                "Each comment must be contextually relevant, natural, and conversational.\n"
                "Do NOT follow a pattern — vary tone, structure, and phrasing.\n"
                "Avoid repetition of words or ideas across comments.\n"
                "No emojis, no punctuation, no hashtags, no quotes, no marketing tone.\n"
                "Comments should feel spontaneous, like real people reacting differently.\n\n"
                f"Tweet: {tweet_text}\n"
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )

            duration = round(time.time() - start_time, 1)
            comments = response.choices[0].message.content.strip()
            results.append({
                "author": author,
                "url": url,
                "tweet_text": tweet_text,
                "comments": comments,
                "processing_time_sec": duration
            })

        except requests.exceptions.Timeout:
            results.append({
                "url": url,
                "error": "⚠️ Request took too long — skipped this tweet."
            })
        except Exception as e:
            results.append({
                "url": url,
                "error": f"⚠️ Error processing tweet: {str(e)}"
            })

    # -------- CLEAN OUTPUT --------
    formatted_output = ""
    for i, r in enumerate(results, start=1):
        formatted_output += f"🔗 {r['url']}\n"
        if "error" in r:
            formatted_output += f"{r['error']}\n"
        else:
            formatted_output += f"{r['comments']}\n"
            formatted_output += f"(⏱ {r['processing_time_sec']}s)\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} tweets.",
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
