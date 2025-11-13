from flask import Flask, request, jsonify, stream_with_context, Response
from openai import OpenAI
import requests, threading, time, random, gc, json

app = Flask(__name__)
client = OpenAI()

# ---------- KEEP SERVER AWAKE ----------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/")
            print("✅ Ping sent to keep server awake.")
        except Exception as e:
            print("⚠️ Ping failed:", e)
        time.sleep(15 * 60)

threading.Thread(target=keep_alive, daemon=True).start()


# ---------- COMMENT GENERATOR ----------
def generate_comments_with_retry(prompt, max_retries=5):
    delay = 5
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1}/{max_retries} failed: {e}")
            if "429" in str(e) or "Rate limit" in str(e):
                wait = delay * (2 ** attempt) + random.uniform(3, 6)
                print(f"⏳ Rate limited. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                time.sleep(random.uniform(3, 6))
    print("❌ Max retries reached, skipping.")
    return None


# ---------- HOME ----------
@app.route("/")
def home():
    return "✅ CrownTALK — auto-batching, stable, and human-style comment engine is live."


# ---------- COMMENT ENDPOINT ----------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    urls = [u.strip() for u in urls if u.strip()]
    batch_size = 2
    chunks = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    total_batches = len(chunks)

    def generate():
        all_results = []
        failed_links = []

        for batch_index, batch_urls in enumerate(chunks):
            print(f"🚀 Processing batch {batch_index + 1}/{total_batches}: {batch_urls}")
            batch_output = ""

            for url in batch_urls:
                try:
                    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                    r = requests.get(api_url, timeout=12)
                    data = r.json()
                except Exception as e:
                    failed_links.append(url)
                    continue

                if "text" not in data:
                    failed_links.append(url)
                    continue

                tweet_text = data["text"]

                prompt = (
                    f"Write two short, unique, human-like comments (5–10 words each) reacting to this tweet:\n"
                    f"---\n{tweet_text}\n---\n"
                    f"Rules:\n"
                    f"- No emojis, punctuation, hashtags, or quotes.\n"
                    f"- Avoid repetitive tone, phrasing, or structure.\n"
                    f"- Avoid words: love, feels, excited, finally, curious, this, looks, amazing, skip, feels like.\n"
                    f"- Use slang sparingly (rn, tbh, lowkey, fr, ngl).\n"
                    f"- Must sound casual and distinct.\n"
                    f"- Must end cleanly without punctuation."
                )

                comments = generate_comments_with_retry(prompt)
                if comments:
                    result = f"🔗 [{url}]({url})\n{comments}\n{'─' * 40}\n"
                    all_results.append(result)
                    batch_output += result
                else:
                    failed_links.append(url)

                time.sleep(random.uniform(1.5, 3))
                gc.collect()

            yield f"Batch {batch_index + 1}/{total_batches} complete:\n{batch_output}\n"
            time.sleep(random.uniform(8, 12))  # cooldown

        if failed_links:
            yield f"\n⚠️ Failed links after retry: {json.dumps(failed_links)}\n"
        yield "\n✅ All batches complete!\n"

    return Response(stream_with_context(generate()), mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
