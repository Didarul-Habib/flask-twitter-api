import requests
from flask import Flask, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------- Helpers ----------

def fetch_tweet_data(url):
    """Fetch tweet data using vxTwitter (free public API)."""
    try:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        r = requests.get(api_url, timeout=10)
        data = r.json()
        if "text" not in data:
            return None
        return {"text": data["text"], "author": data.get("user_screen_name", "unknown")}
    except Exception:
        return None


def generate_comments(tweet_text):
    """Generate 2 short (4–8 word) natural comments."""
    prompt = (
        f"Write two separate, natural comments reacting to this tweet.\n"
        f"Each should be 4–8 words long, human-like, and on separate lines.\n"
        f"No hashtags, emojis, or marketing tone.\n\nTweet:\n{tweet_text}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


# ---------- Main Endpoint ----------

@app.route("/comment", methods=["POST"])
def comment():
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"error": "Please provide at least one tweet URL."}), 400
    if len(urls) > 5:
        return jsonify({"error": "You can submit up to 5 tweet links only."}), 400

    seen = set()
    duplicates = [url for url in urls if url in seen or seen.add(url)]
    if duplicates:
        return jsonify({
            "error": f"Duplicate link(s) detected: {', '.join(duplicates)}. Each URL must be unique."
        }), 400

    results = []
    formatted = []

    for i, url in enumerate(urls, start=1):
        tweet = fetch_tweet_data(url)
        if tweet:
            comments = generate_comments(tweet["text"])
            results.append({
                "tweet_url": url,
                "tweet": tweet["text"],
                "comments": comments
            })
            formatted.append(f"🧵 **Tweet {i}:** {url}\n{comments.strip()}\n")
        else:
            results.append({
                "tweet_url": url,
                "comments": "⚠️ Could not fetch this tweet."
            })
            formatted.append(f"🧵 **Tweet {i}:** {url}\n⚠️ Could not fetch this tweet.\n")

    return jsonify({
        "formatted_output": "\n\n".join(formatted),
        "results": results
    })


@app.route("/")
def home():
    return jsonify({
        "message": "Server is running 🚀",
        "usage": "POST /comment with {'urls': ['tweet1', 'tweet2', ...]} (max 5 unique links)"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
