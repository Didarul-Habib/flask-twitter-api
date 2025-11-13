from flask import Flask, request, jsonify
from openai import OpenAI
import requests, time, threading

app = Flask(__name__)
client = OpenAI()

# Global status
progress_status = {
    "status": "idle",
    "current_batch": 0,
    "total_batches": 0,
    "percent_done": 0,
    "eta_seconds": 0
}

def update_progress(current, total):
    progress_status["current_batch"] = current
    progress_status["total_batches"] = total
    progress_status["percent_done"] = round((current / total) * 100, 1)
    progress_status["eta_seconds"] = (total - current) * 12  # rough ETA
    progress_status["status"] = "running" if current < total else "complete"


@app.route("/")
def home():
    return "✅ CrownTalk Comment Generator API is live."


@app.route("/progress", methods=["GET"])
def progress():
    """Return current progress to GPT."""
    return jsonify(progress_status)


@app.route("/comment", methods=["POST", "GET"])
def comment():
    urls = request.args.getlist("url") or request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    # limit to 30 links per run
    if len(urls) > 30:
        return jsonify({"error": "Too many links at once (max 30)."}), 400

    batch_size = 2
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    results, failed_links = [], []

    progress_status.update({
        "status": "running",
        "current_batch": 0,
        "total_batches": len(batches),
        "percent_done": 0,
    })

    def fetch_tweet(url):
        try:
            api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
            r = requests.get(api_url, timeout=10)
            data = r.json()
            if "text" not in data:
                return None, None
            return data.get("user_screen_name"), data["text"]
        except Exception:
            return None, None

    def generate_comments(prompt, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                wait = 10 * (attempt + 1)
                print(f"⚠️ Retry {attempt+1}/{max_retries} after error: {e}")
                time.sleep(wait)
        return None

    start_time = time.time()

    for i, batch in enumerate(batches, start=1):
        print(f"▶️ Processing batch {i}/{len(batches)}...")
        update_progress(i - 1, len(batches))

        for url in batch:
            author, tweet_text = fetch_tweet(url)
            if not tweet_text:
                failed_links.append(url)
                continue

            prompt = (
                f"Write two unique short comments (5–10 words each) based on this tweet:\n"
                f"{tweet_text}\n\n"
                f"Rules:\n"
                f"- No repetition or pattern reuse between comments.\n"
                f"- No emojis or punctuation.\n"
                f"- Avoid overused phrases like love, finally, curious, interesting, this.\n"
                f"- Each comment must sound human and natural, not robotic.\n"
                f"- No label headings, just plain text."
            )

            comments = generate_comments(prompt)
            if comments:
                results.append({"url": url, "author": author, "comments": comments})
            else:
                failed_links.append(url)

        update_progress(i, len(batches))
        time.sleep(12)  # cooldown between batches

    progress_status["status"] = "complete"
    total_time = round(time.time() - start_time, 1)

    return jsonify({
        "summary": f"✅ Processed {len(urls)} tweets in {len(batches)} batches.",
        "time_taken_sec": total_time,
        "results": results,
        "failed_links": failed_links,
        "note": "You can retry failed links separately later."
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
