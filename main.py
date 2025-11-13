from flask import Flask, request, Response, jsonify
from openai import OpenAI
import requests, time, json, re, threading

app = Flask(__name__)
client = OpenAI()

# --- Keep Alive Ping ---
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/")
        except Exception:
            pass
        time.sleep(15 * 60)

threading.Thread(target=keep_alive, daemon=True).start()

# --- Disable buffering for live response ---
@app.after_request
def disable_buffering(response):
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response

# --- Helper to clean tweet URLs ---
def clean_url(url):
    return re.sub(r"\?.*", "", url.strip())

# --- Generate with retry ---
def generate_comments_with_retry(prompt, retries=3, delay=10):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=120
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return f"⚠️ Generation failed: {e}"

@app.route("/")
def home():
    return "✅ CrownTALK Comment Generator active."

# --- Main comment route ---
@app.route("/comment", methods=["POST"])
def comment():
    data = request.get_json()
    urls = [clean_url(u) for u in data.get("urls", [])]

    if not urls:
        return jsonify({"error": "Please provide at least one valid X post URL."}), 400

    def generate():
        batch_size = 2
        total_batches = (len(urls) + batch_size - 1) // batch_size
        failed_links = []

        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_results = []

            yield f"\n\n🌀 Processing batch {i//batch_size + 1}/{total_batches}...\n"

            for url in batch:
                try:
                    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                    r = requests.get(api_url)
                    data = r.json()

                    if "text" not in data:
                        failed_links.append(url)
                        continue

                    tweet_text = data["text"]
                    author = data.get("user_screen_name", "unknown")

                    prompt = (
                        f"Write two short, human-like comments (5–10 words max) reacting to this tweet:\n"
                        f"{tweet_text}\n\n"
                        f"Rules:\n"
                        f"- Do not repeat phrasing or structure between comments.\n"
                        f"- Avoid filler words like 'finally', 'curious', 'love that', 'game changer', 'excited', 'this', 'feels like'.\n"
                        f"- No emojis, punctuation, hashtags, or exclamation marks.\n"
                        f"- Must sound natural, fluent, and not robotic.\n"
                        f"- End each comment naturally without periods."
                    )

                    comments = generate_comments_with_retry(prompt)
                    batch_results.append(f"🔗 {url}\n{comments}\n" + "─" * 45)

                except Exception as e:
                    failed_links.append(url)

            yield "\n".join(batch_results) + "\n"

            if i + batch_size < len(urls):
                yield f"\n⏳ Waiting before next batch...\n"
                time.sleep(3)

        if failed_links:
            yield f"\n⚠️ Failed to process:\n" + "\n".join(failed_links) + "\n"

        yield "\n✅ All batches complete!\n"

    return Response(generate(), mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
