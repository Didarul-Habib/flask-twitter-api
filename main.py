import requests
from flask import Flask, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- Helpers ----------

def fetch_tweet_data(url):
    """Use vxTwitter to fetch tweet content."""
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
    """Generate 2 short (4–8 words) human-like comments."""
    prompt = (
        f"Write two separate short comments (4–8 words each) reacting naturally to this tweet:\n\n"
        f"\"{tweet_text}\"\n\n"
        f"Each comment should be on its own line, no hashtags, no emojis."
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

    # Check duplicates
    seen = set()
    duplicates = [url for url in urls if url in seen or seen.add(url)]
    if duplicates:
        return jsonify({
            "error": f"Duplicate link(s) detected: {', '.join(duplicates)}. Each URL must be unique."
        }), 400

    # Process each link
    results = []
    for url in urls:
        tweet = fetch_tweet_data(url)
        if tweet:
            comments = generate_comments(tweet["text"])
            results.append({"tweet": tweet["text"], "comments": comments})
        else:
            results.append({"tweet": url, "comments": "⚠️ Could not fetch this tweet."})

    return jsonify({"results": results})


@app.route("/")
def home():
    return jsonify({
        "message": "Server is running 🚀",
        "usage": "POST /comment with {'urls': ['tweet1', 'tweet2', ...]} (max 5)"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
