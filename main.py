from flask import Flask, request, jsonify
from openai import OpenAI
import requests, threading, time, re

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
        time.sleep(10 * 60)  # every 10 minutes

threading.Thread(target=keep_alive, daemon=True).start()

# -------- BASIC ROUTE --------
@app.route("/")
def home():
    return "✅ CrownTALK server is active and ready!"

# -------- AI COMMENT GENERATOR WITH RETRIES --------
def generate_comments_with_retry(prompt, retries=3, delay=8):
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # stable and lightweight
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You're CrownTALK, a social AI trained to write short, human-like comments. "
                            "Avoid repeating patterns or filler words like 'game changer', 'finally', 'love to see', "
                            "'excited', 'curious', 'amazing', 'great', 'love that', or 'can't wait'. "
                            "Comments must be natural, unique, and vary in tone. Avoid emojis, punctuation, or repetition. "
                            "Each comment 5–10 words max. No colon or labels. Strictly 2 lines per post."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=1,
                max_tokens=70,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Attempt {attempt+1} failed:", e)
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return None

# -------- COMMENT ENDPOINT --------
@app.route("/comment", methods=["POST"])
def comment():
    try:
        urls = request.json.get("urls", [])
        if not urls:
            return jsonify({"error": "No tweet URLs provided."}), 400

        # Clean and deduplicate
        cleaned_urls = []
        for u in urls:
            u = u.strip()
            u = re.sub(r"\?.*$", "", u)  # remove everything after ?
            if u not in cleaned_urls:
                cleaned_urls.append(u)

        all_results = []
        failed_links = []

        # Process in batches of 2
        batch_size = 2
        total_batches = (len(cleaned_urls) + batch_size - 1) // batch_size

        for i in range(0, len(cleaned_urls), batch_size):
            batch = cleaned_urls[i:i + batch_size]
            print(f"Processing batch {i//batch_size+1}/{total_batches}: {batch}")
            batch_results = []

            for url in batch:
                try:
                    api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
                    r = requests.get(api_url, timeout=10)
                    data = r.json()

                    if "text" not in data:
                        failed_links.append(url)
                        continue

                    tweet_text = data["text"]

                    prompt = (
                        f"Generate 2 short natural comments based on this tweet:\n"
                        f"Tweet: {tweet_text}\n"
                        f"Make both comments sound human, context-aware, and natural."
                    )

                    comments = generate_comments_with_retry(prompt)
                    if not comments:
                        failed_links.append(url)
                        continue

                    batch_results.append({
                        "url": url,
                        "comments": comments
                    })

                except Exception as e:
                    failed_links.append(url)
                    print(f"Error processing {url}:", e)
                    continue

            all_results.extend(batch_results)
            time.sleep(10)  # delay between batches

        # Format results
        formatted_output = ""
        for r in all_results:
            formatted_output += f"🔗 {r['url']}\n{r['comments']}\n" + ("─" * 40 + "\n")

        return jsonify({
            "summary": f"Processed {len(all_results)} tweets in {total_batches} batches.",
            "failed_links": failed_links,
            "formatted": formatted_output.strip()
        })

    except Exception as e:
        print("Critical error:", e)
        return jsonify({"error": "Server internal error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
