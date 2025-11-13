from flask import Flask, request, jsonify, Response, stream_with_context
import requests
import time
import random
import os
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- Comment Generator (with Retry) ----------
def generate_comments_with_retry(prompt, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are CrownTALK, an AI trained to write natural, human-like X (Twitter) comments. "
                            "You NEVER use cliché or repetitive phrasing."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.95,
                max_tokens=70,
            )
            text = response.choices[0].message.content.strip()
            return text.replace("\n\n", "\n").strip()
        except Exception as e:
            print(f"⚠️ Error generating comment (attempt {attempt+1}): {e}")
            time.sleep(delay + random.uniform(2, 6))
    return None


# ---------- /comment Route ----------
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
        failed_links = []

        for i, batch_urls in enumerate(chunks):
            print(f"🚀 Processing batch {i + 1}/{total_batches}: {batch_urls}")
            batch_output = []

            for url in batch_urls:
                try:
                    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                    r = requests.get(api_url, timeout=12)
                    if r.status_code != 200:
                        failed_links.append(url)
                        continue

                    data = r.json()
                    tweet_text = data.get("text", None)
                    if not tweet_text:
                        failed_links.append(url)
                        continue
                except Exception as e:
                    print(f"❌ Error fetching tweet {url}: {e}")
                    failed_links.append(url)
                    continue

                # --- Improved prompt ---
                prompt = (
                    f"Write two short human-like comments (5–10 words each) reacting to this tweet:\n"
                    f"{tweet_text}\n\n"
                    f"STRICT RULES:\n"
                    f"- Each must sound natural, different tone and flow.\n"
                    f"- No clichés like 'game changer', 'finally', 'can't wait', 'love this', 'amazing', "
                    f"'excited', 'revolutionary', 'huge', 'incredible'.\n"
                    f"- Avoid starting with: 'This', 'Such', 'Love', 'Finally', or 'Looks'.\n"
                    f"- No emojis, punctuation, hashtags, or exclamation marks.\n"
                    f"- Never use repetitive words or similar structure.\n"
                    f"- Keep it casual, realistic, short — like genuine X users chatting."
                )

                comments = generate_comments_with_retry(prompt)
                if comments:
                    formatted_comments = comments.strip()
                    batch_output.append(f"🔗 {url}\n{formatted_comments}\n{'─' * 35}")
                else:
                    failed_links.append(url)

                # random rest between tweets
                time.sleep(random.uniform(1.5, 3))

            # send per-batch results
            yield f"\n✅ Batch {i + 1}/{total_batches} complete:\n" + "\n".join(batch_output) + "\n"

            # cooldown delay between batches
            time.sleep(random.uniform(8, 12))

        # show failed links if any
        if failed_links:
            yield f"\n⚠️ Failed to process these links:\n" + "\n".join(failed_links) + "\n"

        yield "\n🎉 All batches completed successfully!\n"

    return Response(stream_with_context(generate()), mimetype="text/plain")


@app.route("/")
def home():
    return "CrownTALK Comment Generator is live!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
