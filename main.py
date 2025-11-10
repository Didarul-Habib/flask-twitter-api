from flask import Flask, jsonify, request
import snscrape.modules.twitter as s
import re
from openai import OpenAI
import os

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Extract Tweet ID
def extract_tweet_id(url):
    match = re.search(r"status/(\d+)", url)
    return match.group(1) if match else None


# --- Fetch Tweet Text
def fetch_tweet_data(url):
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return None
    try:
        full_url = f"https://x.com/i/web/status/{tweet_id}"
        scraper = s.TwitterTweetScraper(full_url)
        tweet = next(scraper.get_items(), None)
        if tweet:
            return {"author": tweet.user.username, "content": tweet.content}
        return None
    except Exception:
        return None


# --- Generate Comment (4–8 words)
def generate_comment(tweet):
    prompt = (
        f"Write one short human-like comment (4–8 words) "
        f"based on this tweet by @{tweet['author']}:\n"
        f"{tweet['content']}\n\n"
        f"Do not include hashtags, emojis, or quotes."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# --- Main Route: handle up to 5 URLs
@app.route("/comment", methods=["POST"])
def comment_multiple():
    data = request.get_json()
    urls = data.get("urls", [])

    if len(urls) == 0:
        return jsonify({"error": "Please provide at least one URL."}), 400
    if len(urls) > 5:
        return jsonify({"error": "You can submit up to 5 links at once."}), 400

    # Duplicate check
    seen = set()
    duplicates = [url for url in urls if url in seen or seen.add(url)]
    if duplicates:
        return jsonify({
            "error": f"Duplicate link(s) detected: {', '.join(duplicates)}. Each URL must be unique."
        }), 400

    comments = []
    for url in urls:
        tweet_data = fetch_tweet_data(url)
        if tweet_data:
            comments.append(generate_comment(tweet_data))
        else:
            comments.append("⚠️ Could not fetch this tweet (private or deleted).")

    return jsonify({"comments": comments})


@app.route("/")
def home():
    return jsonify({
        "message": "Server is running 🚀",
        "usage": "POST /comment with {urls: [tweet_links]}"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
