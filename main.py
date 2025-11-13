from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random, math

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
        time.sleep(15 * 60)  # every 15 minutes

threading.Thread(target=keep_alive, daemon=True).start()


# -------- SMART COMMENT GENERATOR --------
def generate_comments_with_retry(prompt, max_retries=5):
    """Retry with exponential backoff when API fails"""
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
            if attempt < max_retries - 1:
                sleep_for = delay * (2 ** attempt) + random.uniform(1, 3)
                print(f"Retrying in {sleep_for:.1f}s...")
                time.sleep(sleep_for)
            else:
                print("❌ Max retries reached. Skipping this tweet.")
                return None


# -------- HOME ROUTE --------
@app.route("/")
def home():
    return "✅ CrownTALK AI comment generator running smoothly."


# -------- COMMENT ROUTE --------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.json
    all_urls = data.get("urls", [])
    if not all_urls:
        return jsonify({"error": "Please provide at least one tweet URL."}), 400

    batch_size = 2
    total_batches = math.ceil(len(all_urls) / batch_size)

    all_results = []
    failed_links = []

    for batch_index in range(total_batches):
        batch_urls = all_urls[batch_index * batch_size:(batch_index + 1) * batch_size]
        print(f"\n🚀 Starting batch {batch_index + 1}/{total_batches}: {batch_urls}")

        for url in batch_urls:
            try:
                api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                r = requests.get(api_url, timeout=15)
                data = r.json()
            except Exception as e:
                print(f"❌ Fetch failed for {url}: {e}")
                failed_links.append(url)
                continue

            if "text" not in data:
                print(f"⚠️ Missing text for {url}")
                failed_links.append(url)
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = (
                f"Generate 2 unique, human-sounding short comments (5–10 words each) "
                f"based on this tweet:\n---\n{tweet_text}\n---\n"
                f"Rules:\n"
                f"- No emojis or punctuation like '.' or ','.\n"
                f"- No repetitive phrases (love this, finally, excited, feels, curious, amazing, skip, etc.).\n"
                f"- Avoid starting both comments with the same word.\n"
                f"- Use casual tone naturally (rn, fr, btw, tbh, lowkey) but not every time.\n"
                f"- Must sound like two *different humans* replying authentically."
            )

            comments = generate_comments_with_retry(prompt)
            if comments:
                all_results.append({
                    "author": author,
                    "url": url,
                    "tweet_text": tweet_text,
                    "comments": comments
                })
            else:
                failed_links.append(url)

            time.sleep(random.uniform(2, 4))  # between tweets

        # pause before next batch to avoid rate limits
        if batch_index < total_batches - 1:
            wait_time = random.uniform(8, 15)
            print(f"✅ Batch {batch_index + 1} done. Waiting {wait_time:.1f}s before next.")
            time.sleep(wait_time)

    # -------- FORMAT FINAL RESPONSE --------
    formatted_output = ""
    for r in all_results:
        formatted_output += f"🔗 {r['url']}\n{r['comments']}\n{'─' * 40}\n"

    if not all_results and failed_links:
        return jsonify({
            "error": "⚠️ Comment generator is temporarily unavailable. Auto-retry failed. Try again later.",
            "failed_links": failed_links
        }), 503

    return jsonify({
        "summary": f"Processed {len(all_results)} tweets. Failed: {len(failed_links)}",
        "failed_links": failed_links,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
