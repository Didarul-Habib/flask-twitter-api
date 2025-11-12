from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random

app = Flask(__name__)
client = OpenAI()

# -------- GLOBAL STATUS TRACKER --------
progress_state = {
    "current_batch": 0,
    "total_batches": 0,
    "eta_seconds": 0,
    "percent_done": 0,
    "status": "idle"
}

# -------- KEEP SERVER AWAKE --------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/health")
            print("🔄 Pinged /health successfully to keep alive.")
        except Exception as e:
            print("⚠️ Ping failed:", e)
        time.sleep(10 * 60)

threading.Thread(target=keep_alive, daemon=True).start()

# -------- AUTO LOG CLEANER --------
def clear_logs_every_12h():
    while True:
        try:
            print("🧹 Clearing old logs to keep Render lightweight...")
            open("server_log.txt", "w").close()
            time.sleep(1)
            print("✅ Logs cleared successfully.")
        except Exception as e:
            print("⚠️ Log cleanup failed:", e)
        time.sleep(12 * 60 * 60)

threading.Thread(target=clear_logs_every_12h, daemon=True).start()

# -------- HEALTH CHECK --------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "uptime": "✅ CrownTalk active and stable"}), 200

# -------- PROGRESS CHECK ENDPOINT --------
@app.route("/progress")
def progress():
    """Return real-time progress info"""
    return jsonify(progress_state)

# -------- RETRY HELPER --------
def fetch_tweet_data(url, retries=2):
    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
    for attempt in range(retries + 1):
        try:
            r = requests.get(api_url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if "text" in data:
                    return data
            print(f"⚠️ Retry {attempt + 1}/{retries} failed for {url}")
            time.sleep(1.5)
        except Exception as e:
            print(f"❌ Fetch error for {url}: {e}")
            time.sleep(1.5)
    return None


# -------- COMMENT GENERATOR --------
@app.route("/comment", methods=["GET", "POST"])
def comment():
    urls = request.args.getlist("url") or request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    unique_urls, duplicates = [], []
    for u in urls:
        if u not in unique_urls:
            unique_urls.append(u)
        else:
            duplicates.append(u)

    batch_size = 4
    delay_between_batches = 3
    est_time_per_tweet = 6
    results = []
    total_batches = (len(unique_urls) + batch_size - 1) // batch_size

    progress_state.update({
        "current_batch": 0,
        "total_batches": total_batches,
        "eta_seconds": 0,
        "percent_done": 0,
        "status": "running"
    })

    print(f"📦 Starting processing for {len(unique_urls)} tweets, {total_batches} batches total.")
    progress_summary = []
    start_time = time.time()

    for i in range(0, len(unique_urls), batch_size):
        batch = unique_urls[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_left = len(unique_urls) - i
        eta_seconds = total_left * est_time_per_tweet

        # Update live progress
        progress_state.update({
            "current_batch": batch_num,
            "eta_seconds": eta_seconds,
            "percent_done": round((batch_num - 1) / total_batches * 100, 1),
        })

        progress_msg = f"Batch {batch_num}/{total_batches} running (ETA ~{eta_seconds}s)"
        print(f"\n🚀 {progress_msg}")
        progress_summary.append(progress_msg)

        for url in batch:
            data = fetch_tweet_data(url)
            if not data:
                results.append({
                    "url": url,
                    "error": "⚠️ Could not fetch this tweet (private/deleted/timeout)."
                })
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = f"""
You are a natural, intelligent social media commenter.  
Generate two short, realistic, and unique comments for the tweet below.

Tweet:
{tweet_text}

Rules:
- Each comment must be 5–10 words.
- No punctuation or emojis.
- Avoid repetitive or common words like finally, curious, love that, loving, this, amazing, great, awesome, nice, cool.
- Do not start two comments the same way.
- Never use same word twice in both comments.
- Randomize tone: thoughtful, witty, chill, confident, or casual (fr, ngl, lowkey, rn, kinda).
- Each comment must sound like it’s written by different real humans.
Return only the comments on separate lines.
"""

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=random.uniform(1.2, 1.6),
                )

                comments = [
                    c.strip("•- ") for c in response.choices[0].message.content.strip().split("\n") if c.strip()
                ]
                results.append({
                    "author": author,
                    "url": url,
                    "tweet_text": tweet_text,
                    "comments": comments
                })

                print(f"✅ Processed @{author} — {len(comments)} comments ready.")

            except Exception as e:
                results.append({
                    "url": url,
                    "error": f"Server error: {str(e)}"
                })

        # Update percentage after each batch
        progress_state["percent_done"] = round(batch_num / total_batches * 100, 1)

        if i + batch_size < len(unique_urls):
            print(f"⏳ Waiting {delay_between_batches}s before next batch...\n")
            time.sleep(delay_between_batches)

    duration = round(time.time() - start_time, 2)
    progress_state.update({
        "status": "complete",
        "eta_seconds": 0,
        "percent_done": 100
    })

    formatted_output = ""
    for r in results:
        formatted_output += f"🔗 {r['url']}\n"
        if "error" in r:
            formatted_output += f"{r['error']}\n"
        else:
            for c in r["comments"]:
                formatted_output += f"- {c}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} tweets in {duration}s.",
        "progress": progress_summary,
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
