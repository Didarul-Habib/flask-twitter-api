from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random

app = Flask(__name__)
client = OpenAI()

progress_state = {"current_batch": 0, "total_batches": 0, "eta_seconds": 0, "percent_done": 0, "status": "idle"}

# ----------------- Keep Server Alive -----------------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/health")
            print("🔄 Ping sent to keep alive.")
        except Exception as e:
            print("⚠️ Ping failed:", e)
        time.sleep(10 * 60)

threading.Thread(target=keep_alive, daemon=True).start()


# ----------------- Auto Log Cleanup -----------------
def clear_logs_every_12h():
    while True:
        try:
            print("🧹 Clearing logs...")
            open("server_log.txt", "w").close()
        except Exception as e:
            print("⚠️ Log cleanup failed:", e)
        time.sleep(12 * 60 * 60)

threading.Thread(target=clear_logs_every_12h, daemon=True).start()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "CrownTalk is alive"}), 200


# ----------------- Retry Logic for Fetch -----------------
def fetch_tweet_data(url, retries=3):
    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
    backoff = 1
    for attempt in range(retries):
        try:
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "text" in data:
                    return data
            print(f"⚠️ Fetch failed (Attempt {attempt+1}/{retries}) for {url}")
        except Exception as e:
            print(f"❌ Fetch error ({attempt+1}): {e}")
        time.sleep(backoff)
        backoff *= 2  # exponential wait
    return None


# ----------------- Retry Logic for GPT -----------------
def generate_comments_with_retry(prompt, retries=3):
    backoff = 2
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=random.uniform(1.2, 1.6),
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ GPT error (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(backoff)
            backoff *= 2
    return None


# ----------------- Main Comment Endpoint -----------------
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

    results = []
    batch_size = 4
    progress_state.update({
        "status": "running",
        "current_batch": 0,
        "total_batches": (len(unique_urls) + batch_size - 1) // batch_size,
        "percent_done": 0
    })

    start_time = time.time()

    for i in range(0, len(unique_urls), batch_size):
        batch = unique_urls[i:i + batch_size]
        progress_state["current_batch"] = i // batch_size + 1

        for url in batch:
            data = fetch_tweet_data(url)
            if not data:
                results.append({"url": url, "error": "⚠️ Could not fetch tweet (private/deleted)."})
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            prompt = f"""
Generate two short, natural, non-repetitive comments (5–10 words) reacting to this tweet:

Tweet:
{tweet_text}

Rules:
- No punctuation or emojis
- Avoid overused words like finally, curious, love that, this, amazing, etc
- Each comment should sound like a real human (casual, witty, confident, chill, or short influencer tone)
- Never repeat structure or phrasing across comments
Output comments on separate lines only
"""

            comments = generate_comments_with_retry(prompt)
            if not comments:
                results.append({"url": url, "error": "⚠️ GPT temporarily unavailable, try again."})
                continue

            results.append({
                "author": author,
                "url": url,
                "tweet_text": tweet_text,
                "comments": comments.split("\n")
            })

        progress_state["percent_done"] = round(
            (progress_state["current_batch"] / progress_state["total_batches"]) * 100, 1
        )

    duration = round(time.time() - start_time, 2)
    progress_state["status"] = "complete"

    formatted_output = ""
    for r in results:
        formatted_output += f"🔗 {r['url']}\n"
        if "error" in r:
            formatted_output += f"{r['error']}\n"
        else:
            for c in r["comments"]:
                formatted_output += f"- {c.strip()}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} tweets in {duration}s.",
        "duplicates_ignored": duplicates,
        "formatted": formatted_output.strip()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
