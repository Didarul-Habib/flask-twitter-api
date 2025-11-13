from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random, math, gc

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
        time.sleep(15 * 60)  # every 15 min

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
            text = response.choices[0].message.content.strip()
            return text
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1}/{max_retries} failed: {e}")
            if "429" in str(e) or "Rate limit" in str(e):
                wait = delay * (2 ** attempt) + random.uniform(3, 6)
                print(f"⏳ Rate limited. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                time.sleep(random.uniform(3, 6))
    print("❌ Max retries reached, skipping this one.")
    return None


# ---------- HOME ----------
@app.route("/")
def home():
    return "✅ CrownTALK — Comment engine stable & optimized."


# ---------- COMMENT ENDPOINT ----------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    batch_size = 2
    total_batches = math.ceil(len(urls) / batch_size)
    all_results, failed_links = [], []

    for batch_index in range(total_batches):
        batch_urls = urls[batch_index * batch_size:(batch_index + 1) * batch_size]
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
                failed_links.append(url)
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = (
                f"Write two different short human-like comments (5–10 words each) reacting to this tweet:\n"
                f"---\n{tweet_text}\n---\n"
                f"Rules:\n"
                f"- No emojis, punctuation, hashtags, or quotes.\n"
                f"- Avoid repetitive tone or structure.\n"
                f"- Avoid words like love, feels, excited, finally, curious, this, looks, amazing.\n"
                f"- Each comment must sound natural, unique, and casual.\n"
                f"- Randomly use slang like rn, tbh, lowkey, fr, ngl—but not always.\n"
                f"- Never repeat the same phrasing across tweets."
            )

            comment_text = generate_comments_with_retry(prompt)
            if comment_text:
                all_results.append({
                    "author": author,
                    "url": url,
                    "comments": comment_text
                })
            else:
                failed_links.append(url)

            time.sleep(random.uniform(1.5, 3))
            gc.collect()

        # Cooldown between batches
        if batch_index < total_batches - 1:
            rest_time = random.uniform(8, 12)
            print(f"🕐 Cooling down for {rest_time:.1f}s...")
            time.sleep(rest_time)

    # Retry failed ones once
    if failed_links:
        print("🔁 Retrying failed links...")
        retry_results, still_failed = [], []
        for url in failed_links:
            try:
                api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                r = requests.get(api_url, timeout=12)
                data = r.json()
                if "text" not in data:
                    still_failed.append(url)
                    continue

                tweet_text = data["text"]
                prompt = (
                    f"Write two distinct short human-like comments (5–10 words each) reacting to:\n"
                    f"{tweet_text}\n"
                    f"No emojis, hashtags, or punctuation. No repeating words or tone."
                )

                comment_text = generate_comments_with_retry(prompt)
                if comment_text:
                    retry_results.append({
                        "url": url,
                        "comments": comment_text
                    })
                else:
                    still_failed.append(url)
            except Exception as e:
                print(f"⚠️ Retry failed for {url}: {e}")
                still_failed.append(url)

        all_results.extend(retry_results)
        failed_links = still_failed

    formatted_output = ""
    for r in all_results:
        formatted_output += f"🔗 {r['url']}\n{r['comments']}\n{'─' * 40}\n"

    return jsonify({
        "summary": f"✅ {len(all_results)} tweets processed. {len(failed_links)} failed after retry.",
        "failed_links": failed_links,
        "formatted": formatted_output[-2000:]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
