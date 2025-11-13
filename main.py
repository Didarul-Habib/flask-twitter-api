from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, random, re

app = Flask(__name__)
client = OpenAI()

# -------- KEEP SERVER AWAKE --------
def keep_alive():
    while True:
        try:
            requests.get("https://flask-twitter-api.onrender.com/")
            print("💤 Ping sent to keep server awake.")
        except Exception as e:
            print("⚠️ Ping failed:", e)
        time.sleep(15 * 60)  # every 15 min

threading.Thread(target=keep_alive, daemon=True).start()

# -------- HELPER: CLEAN URL --------
def clean_url(url):
    """Remove tracking or extra params after '?'."""
    return url.split("?")[0].strip()

# -------- HELPER: RETRY SAFE COMMENT GENERATOR --------
def generate_comments(prompt, retries=4):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                timeout=90,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Error attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                wait = random.uniform(10, 25)
                print(f"⏳ Waiting {int(wait)}s before retry...")
                time.sleep(wait)
    return None  # if still fails after retries

# -------- HOME --------
@app.route("/")
def home():
    return jsonify({"status": "✅ CrownTALK server is active and ready!"})

# -------- COMMENT ENDPOINT --------
@app.route("/comment", methods=["POST"])
def comment():
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"error": "No tweet URLs provided."}), 400

    # remove duplicates and clean urls
    cleaned_urls, duplicates = [], []
    for u in urls:
        cu = clean_url(u)
        if cu not in cleaned_urls:
            cleaned_urls.append(cu)
        else:
            duplicates.append(cu)

    batch_size = 2
    results, failed_batches = [], []

    print(f"🔄 Received {len(cleaned_urls)} total links for processing.")

    # process in batches of 2
    for i in range(0, len(cleaned_urls), batch_size):
        batch = cleaned_urls[i:i + batch_size]
        print(f"⚙️ Processing batch {i//batch_size + 1}/{(len(cleaned_urls)+1)//batch_size}:", batch)
        batch_results = []

        for url in batch:
            api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
            try:
                r = requests.get(api_url, timeout=15)
                data = r.json()
            except Exception as e:
                batch_results.append({
                    "url": url,
                    "error": f"❌ API error: {str(e)}"
                })
                continue

            if "text" not in data:
                batch_results.append({
                    "url": url,
                    "error": "⚠️ Could not fetch tweet (private or deleted)."
                })
                continue

            tweet_text = data["text"]
            author = data.get("user_screen_name", "unknown")

            # STRONG STYLE INSTRUCTIONS
            prompt = (
                f"Act like a smart human influencer writing short X comments.\n"
                f"Write 2 short natural comments (5–10 words each) for this post:\n"
                f"{tweet_text}\n\n"
                f"Rules:\n"
                f"- No emojis, punctuation, or quotation marks.\n"
                f"- Avoid overused words like 'game changer', 'finally', 'excited', 'love that', 'feels like', 'this is huge', 'curious'.\n"
                f"- Use casual expressions naturally (like 'tbh', 'fr', 'btw', 'lowkey') only if it fits.\n"
                f"- Each comment must sound unique and human.\n"
                f"- Never use same pattern or start with the same word.\n"
                f"- Output just the comments, no labels or numbering."
            )

            comments = generate_comments(prompt)
            if comments:
                batch_results.append({
                    "author": author,
                    "url": url,
                    "comments": comments
                })
            else:
                batch_results.append({
                    "url": url,
                    "error": "⚠️ Comment generation failed after retries."
                })
                failed_batches.append(url)

            # short cooldown to reduce API strain
            time.sleep(random.uniform(5, 10))

        results.extend(batch_results)

        # show after every batch
        print(f"✅ Batch {i//batch_size + 1} complete.")

    formatted_output = ""
    for r in results:
        formatted_output += f"🔗 {r['url']}\n"
        if "error" in r:
            formatted_output += f"{r['error']}\n"
        else:
            formatted_output += f"{r['comments']}\n"
        formatted_output += "─" * 40 + "\n"

    return jsonify({
        "summary": f"Processed {len(results)} links.",
        "duplicates_ignored": duplicates,
        "failed_to_generate": failed_batches,
        "formatted": formatted_output.strip()
    })

# -------- MAIN --------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
