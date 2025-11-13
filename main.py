from flask import Flask, request, jsonify
from openai import OpenAI
import requests, time, re

app = Flask(__name__)
client = OpenAI()

# -------- CLEAN URL --------
def clean_url(url):
    return re.sub(r"\?.*", "", url.strip())

# -------- SAFE OPENAI REQUEST WITH RETRY --------
def generate_comments_with_retry(prompt, retries=3, delay=10):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                raise
    return None

# -------- COMMENT ENDPOINT --------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.get_json()
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "Please provide tweet URLs"}), 400

    cleaned_urls = [clean_url(u) for u in urls]
    total = len(cleaned_urls)
    batch_size = 2
    results = []
    failed = []

    print(f"🔹 Received {total} links")

    for i in range(0, total, batch_size):
        batch = cleaned_urls[i:i+batch_size]
        print(f"⏳ Processing batch {i//batch_size + 1}/{(total+1)//batch_size}: {batch}")
        batch_results = []

        for url in batch:
            try:
                api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                r = requests.get(api_url, timeout=15)
                data = r.json()

                if "text" not in data:
                    failed.append(url)
                    continue

                tweet_text = data["text"]
                author = data.get("user_screen_name", "unknown")

                prompt = f"""
Generate two unique, short, natural comments (5–10 words each) for this tweet:
---
{tweet_text}
---
Strict rules:
- Must sound human, not AI-generated
- No repetition between comments or across batches
- Avoid words like 'finally', 'game changer', 'love this', 'excited', 'curious', 'feels like', 'can't wait', 'great project'
- Never use emojis, hashtags, punctuation (.,!?) or quotes
- No pattern, no colon labels
- Use realistic influencer slang occasionally (like rn, fr, tbh, kinda)
- Each comment must stand on its own
"""

                comments = generate_comments_with_retry(prompt)
                batch_results.append({
                    "url": url,
                    "author": author,
                    "comments": comments
                })
            except Exception as e:
                print(f"❌ Failed: {url} | {e}")
                failed.append(url)

        results.extend(batch_results)
        print(f"✅ Batch {i//batch_size + 1} complete ({len(batch_results)} links).")
        time.sleep(5)

    output_text = ""
    for r in results:
        output_text += f"🔗 {r['url']}\n{r['comments']}\n" + "─" * 40 + "\n"

    if failed:
        output_text += f"\n⚠️ Failed links ({len(failed)}):\n" + "\n".join(failed)

    return jsonify({
        "summary": f"Processed {len(results)} tweets. Failed: {len(failed)}.",
        "output": output_text.strip()
    })


@app.route("/")
def home():
    return "✅ CrownTALK v3.0 — Smart Comment Engine Active."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
