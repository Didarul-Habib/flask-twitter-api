from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random, math

app = Flask(__name__)
client = OpenAI()

# ---------- KEEP SERVER AWAKE ----------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/")
            print("Ping sent to keep server awake.")
        except Exception as e:
            print("Ping failed:", e)
        time.sleep(15 * 60)  # every 15 minutes

threading.Thread(target=keep_alive, daemon=True).start()

# ---------- COMMENT GENERATOR WITH RETRY ----------
def generate_comments_with_retry(prompt, max_retries=4):
    delay = 4
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=50,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1}/{max_retries} failed: {e}")
            if "429" in str(e):
                # API rate limit — wait longer
                wait = delay * (2 ** attempt) + random.uniform(3, 5)
                print(f"Rate limited. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                time.sleep(random.uniform(2, 5))
    print("❌ Max retries reached. Skipping.")
    return None


# ---------- HOME ----------
@app.route("/")
def home():
    return "✅ CrownTALK AI — optimized and live."


# ---------- COMMENT ROUTE ----------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.json
    all_urls = data.get("urls", [])
    if not all_urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    batch_size = 1  # safest for Render free
    total_batches = math.ceil(len(all_urls) / batch_size)

    all_results = []
    failed_links = []

    for batch_index in range(total_batches):
        batch_urls = all_urls[batch_index * batch_size:(batch_index + 1) * batch_size]
        print(f"🚀 Processing batch {batch_index + 1}/{total_batches}: {batch_urls}")

        for url in batch_urls:
            try:
                api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                r = requests.get(api_url, timeout=12)
                data = r.json()
            except Exception as e:
                print(f"❌ Failed to fetch {url}: {e}")
                failed_links.append(url)
                continue

            if "text" not in data:
                print(f"⚠️ No text found for {url}")
                failed_links.append(url)
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = (
                f"Generate two natural, human-like short comments (5–10 words each) about this tweet:\n"
                f"---\n{tweet_text}\n---\n"
                f"Rules:\n"
                f"- No emojis or punctuation (.,!?).\n"
                f"- No repetitive starts like love this, finally, feels, excited, skip, curious.\n"
                f"- Must sound unique and human — not similar tone.\n"
                f"- Avoid same phrases across multiple comments.\n"
                f"- Randomly use slang (fr, tbh, rn, lowkey) but not always.\n"
                f"- Do not repeat structure between comments.\n"
            )

            comments = generate_comments_with_retry(prompt)
            if comments:
                all_results.append({
                    "author": author,
                    "url": url,
                    "comments": comments
                })
            else:
                failed_links.append(url)

            time.sleep(random.uniform(1.5, 3))  # lighter sleep between requests

        # rest between batches (keep Render stable)
        if batch_index < total_batches - 1:
            rest_time = random.uniform(5, 8)
            print(f"Batch {batch_index + 1} done. Cooling for {rest_time:.1f}s.")
            time.sleep(rest_time)

    formatted_output = ""
    for r in all_results:
        formatted_output += f"🔗 {r['url']}\n{r['comments']}\n{'─' * 40}\n"

    return jsonify({
        "summary": f"✅ Done! {len(all_results)} tweets processed. {len(failed_links)} failed.",
        "failed_links": failed_links,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
