from flask import Flask, request, jsonify, Response
from openai import OpenAI
import requests, time, json

app = Flask(__name__)
client = OpenAI()

# ---------- BASIC HOME ----------
@app.route("/")
def home():
    return "✅ CrownTalk Smart Comment Generator is live and stable."

# ---------- FETCH TWEET DATA ----------
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

# ---------- SMART COMMENT GENERATOR ----------
def generate_comments(prompt, max_retries=5):
    """Generate comments with adaptive delay if OpenAI throttles."""
    base_delay = 12  # start delay for rate-limit handling
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_text = str(e).lower()
            if "429" in error_text or "rate" in error_text:
                wait_time = base_delay * (attempt + 1)
                print(f"⚠️ Rate limit detected — waiting {wait_time}s before retry.")
                time.sleep(wait_time)
            else:
                wait_time = 8 * (attempt + 1)
                print(f"⚠️ OpenAI error {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
    print("❌ Max retries reached, skipping tweet.")
    return None

# ---------- MAIN COMMENT ROUTE ----------
@app.route("/comment", methods=["POST", "GET"])
def comment():
    # Collect URLs from query or JSON
    urls = request.args.getlist("url") or request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL"}), 400

    batch_size = 2
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    total_batches = len(batches)
    failed_links = []

    def stream_batches():
        yield "data: 🟢 CrownTalk comment generation started...\n\n"
        start_time = time.time()

        for i, batch in enumerate(batches, start=1):
            yield f"data: ▶️ Processing batch {i} of {total_batches}\n\n"
            batch_results = []
            local_failures = 0

            for url in batch:
                author, tweet_text = fetch_tweet(url)
                if not tweet_text:
                    failed_links.append(url)
                    local_failures += 1
                    continue

                prompt = (
                    f"Write two short, natural comments (5–10 words) reacting to this tweet:\n\n"
                    f"{tweet_text}\n\n"
                    f"Rules:\n"
                    f"- No repetitive structure or similar patterns between comments.\n"
                    f"- Avoid overused phrases: love, finally, curious, this, interesting, amazing.\n"
                    f"- No punctuation, emojis, hashtags, or labels.\n"
                    f"- Must sound natural and written by a human.\n"
                    f"- Two separate lines — one comment per line."
                )

                comments = generate_comments(prompt)
                if comments:
                    batch_results.append({
                        "url": url,
                        "author": author,
                        "comments": comments
                    })
                else:
                    failed_links.append(url)
                    local_failures += 1

            # Send each batch’s output to GPT as it’s ready
            yield f"data: {json.dumps(batch_results, ensure_ascii=False)}\n\n"

            # Smart rest logic to avoid 429s
            if local_failures > 0:
                delay = 20  # give API breathing room
                yield f"data: ⏳ Resting {delay}s before next batch (rate limit cool-down)...\n\n"
            else:
                delay = 10
                yield f"data: ⏳ Resting {delay}s before next batch...\n\n"

            time.sleep(delay)

        duration = round(time.time() - start_time, 1)
        summary = {
            "summary": f"✅ Processed {len(urls)} tweets in {duration}s ({total_batches} batches total).",
            "failed_links": failed_links,
            "note": "Retry failed links separately later if needed."
        }

        yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"
        yield "event: end\ndata: done\n\n"

    return Response(stream_batches(), mimetype="text/event-stream")

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
