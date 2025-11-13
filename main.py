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


# -------- OPENAI RETRY LOGIC --------
def generate_comments_with_retry(prompt, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                sleep_time = delay + random.uniform(1, 3)
                print(f"Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            else:
                return None


# -------- HOME ROUTE --------
@app.route("/")
def home():
    return "✅ CrownTALK is alive and batching smartly."


# -------- COMMENT GENERATOR --------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.json
    all_urls = data.get("urls", [])
    if not all_urls:
        return jsonify({"error": "Please provide at least one tweet URL."}), 400

    batch_size = 2  # process 2 at a time
    total_batches = math.ceil(len(all_urls) / batch_size)

    all_results = []
    failed_links = []

    for batch_index in range(total_batches):
        batch_urls = all_urls[batch_index * batch_size:(batch_index + 1) * batch_size]
        print(f"Processing batch {batch_index + 1}/{total_batches}: {batch_urls}")

        for url in batch_urls:
            api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
            try:
                r = requests.get(api_url, timeout=15)
                data = r.json()
            except Exception as e:
                failed_links.append(url)
                continue

            if "text" not in data:
                failed_links.append(url)
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = (
                f"Generate 2 unique, natural human comments (5–10 words each) reacting to this tweet:\n"
                f"---\n{tweet_text}\n---\n"
                f"Rules:\n"
                f"- Avoid emojis and punctuation like '.' or ','.\n"
                f"- Avoid repetitive or robotic phrasing (love this, finally, feels, curious, excited, skip, amazing, great, etc.).\n"
                f"- Avoid same patterns between comments.\n"
                f"- Use slang naturally (like rn, fr, btw, tbh, lowkey) but not every time.\n"
                f"- Sound like real people tweeting differently each time.\n"
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

            time.sleep(random.uniform(2, 4))  # pause between tweets

        # rest between batches to avoid rate limit
        if batch_index < total_batches - 1:
            print("Batch complete, sleeping before next batch...")
            time.sleep(random.uniform(6, 10))

    # -------- FORMATTING --------
    formatted_output = ""
    for r in all_results:
        formatted_output += f"🔗 {r['url']}\n{r['comments']}\n{'─' * 40}\n"

    return jsonify({
        "summary": f"Processed {len(all_results)} tweets in {total_batches} batches. Failed: {len(failed_links)}",
        "failed_links": failed_links,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
