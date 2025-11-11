from flask import Flask, request, jsonify
from openai import OpenAI
import requests, re, threading, time, os

app = Flask(__name__)

# Initialize OpenAI with env var
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    urls = request.args.getlist("url") or request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    if len(urls) > 5:
        return jsonify({"error": "Maximum 5 links allowed at once."}), 400

    # remove duplicates
    unique_urls, duplicates = [], []
    for u in urls:
        clean_url = re.sub(r'\?.*', '', u.strip())  # clean tracking params
        if clean_url not in unique_urls:
            unique_urls.append(clean_url)
        else:
            duplicates.append(clean_url)

    results = []
    for url in unique_urls:
        try:
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

            # --- Refined prompt for influencer tone ---
            prompt = (
                f"You are a human social media user writing natural short reactions.\n"
                f"Generate TWO distinct comments (5–10 words each) reacting to this tweet:\n"
                f"---\n{tweet_text}\n---\n"
                f"Rules:\n"
                f"- Sound like a smart creator or influencer online.\n"
                f"- Use modern slang when natural (rn, fr, tbh, btw, lowkey, etc.).\n"
                f"- Never repeat word choice, rhythm, or structure.\n"
                f"- No emojis, punctuation, hashtags, or quotes.\n"
                f"- Each comment must be unique and spontaneous.\n"
                f"- Avoid generic filler words like impressive, amazing, great.\n"
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )

            comments = response.choices[0].message.content.strip()
            results.append({
                "author": author,
                "url": url,
                "tweet_text": tweet_text,
                "comments": comments
            })

        except Exception as e:
            results.append({"url": url, "error": str(e)})

    # -------- CLEAN OUTPUT --------
    formatted_output = ""
    for r in results:
        formatted_output += f"🔗 {r['url']}\n"
        formatted_output += f"{r.get('comments', r.get('error'))}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} tweets.",
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
