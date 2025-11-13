from flask import Flask, request, jsonify, Response
from openai import OpenAI
import requests, asyncio, time, json
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
client = OpenAI()
executor = ThreadPoolExecutor(max_workers=3)  # low memory async pool

# ---------- ROOT ----------
@app.route("/")
def home():
    return "✅ CrownTalk v5 — Smart async comment engine with auto retry."

# ---------- FETCH TWEET DATA ----------
def fetch_tweet(url):
    try:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        r = requests.get(api_url, timeout=8)
        data = r.json()
        if "text" not in data:
            return None, None
        return data.get("user_screen_name"), data["text"]
    except Exception:
        return None, None

# ---------- OPENAI COMMENT HANDLER ----------
def openai_comment_call(prompt):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

async def generate_comments(prompt, max_retries=5):
    base_delay = 12
    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(executor, openai_comment_call, prompt)
            return response.choices[0].message.content.strip()
        except Exception as e:
            err = str(e).lower()
            wait_time = base_delay * (attempt + 1)
            print(f"⚠️ OpenAI error: {e}. Waiting {wait_time}s before retry.")
            await asyncio.sleep(wait_time)
    print("❌ Max retries reached. Skipping tweet.")
    return None

# ---------- SHARED COMMENT PROCESSOR ----------
async def process_tweets(urls, is_retry=False):
    batch_size = 2
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    total_batches = len(batches)
    failed_links = []

    start = time.time()
    tag = "♻️ RETRY MODE" if is_retry else "🚀 GENERATE MODE"

    yield f"data: 🟢 CrownTalk {tag} started — processing {len(urls)} tweets\n\n"

    for i, batch in enumerate(batches, start=1):
        yield f"data: ▶️ Batch {i}/{total_batches}...\n\n"
        batch_results = []
        local_fail = 0

        for url in batch:
            author, tweet_text = fetch_tweet(url)
            if not tweet_text:
                failed_links.append(url)
                local_fail += 1
                continue

            prompt = (
                f"Write two short natural comments (5–10 words) for this tweet:\n\n"
                f"{tweet_text}\n\n"
                f"Rules:\n"
                f"- Avoid repetitive tone or patterns.\n"
                f"- Avoid overused words (love, finally, curious, this, amazing).\n"
                f"- No punctuation, emojis, or hashtags.\n"
                f"- Sound natural, like two real people.\n"
                f"- Two comments, each on its own line."
            )

            comments = await generate_comments(prompt)
            if comments:
                batch_results.append({"url": url, "author": author, "comments": comments})
            else:
                failed_links.append(url)
                local_fail += 1

        yield f"data: {json.dumps(batch_results, ensure_ascii=False)}\n\n"

        delay = 20 if local_fail > 0 else 10
        msg = "cool-down" if local_fail > 0 else "normal delay"
        yield f"data: ⏳ Resting {delay}s ({msg})...\n\n"
        await asyncio.sleep(delay)

    duration = round(time.time() - start, 1)
    summary = {
        "summary": f"✅ Finished {len(urls)} tweets in {duration}s ({total_batches} batches).",
        "failed_links": failed_links,
        "note": "Retry these later via /retry if needed."
    }
    yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"
    yield "event: end\ndata: done\n\n"

# ---------- MAIN COMMENT ENDPOINT ----------
@app.route("/comment", methods=["POST"])
def comment():
    urls = request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide tweet URLs"}), 400
    return Response(asyncio.run(process_tweets(urls, is_retry=False)), mimetype="text/event-stream")

# ---------- RETRY ENDPOINT ----------
@app.route("/retry", methods=["POST"])
def retry_failed():
    urls = request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide failed tweet URLs"}), 400
    return Response(asyncio.run(process_tweets(urls, is_retry=True)), mimetype="text/event-stream")

# ---------- RUN SERVER ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
