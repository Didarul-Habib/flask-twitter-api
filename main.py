from flask import Flask, jsonify, request
import os
import re
import requests
from openai import OpenAI

app = Flask(__name__)

# Load API keys from environment
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def extract_tweet_id(url):
    match = re.search(r"status/(\d+)", url)
    return match.group(1) if match else None

def get_tweet_data(tweet_url):
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        return None, {"error": "Invalid tweet URL"}

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    api_url = (
        f"https://api.x.com/2/tweets/{tweet_id}"
        "?expansions=author_id&tweet.fields=created_at,text&user.fields=username"
    )

    r = requests.get(api_url, headers=headers)
    if r.status_code != 200:
        return None, {"error": "Failed to fetch tweet", "details": r.text}
    return r.json(), None

@app.route("/")
def home():
    return jsonify({
        "message": "Server is running",
        "usage": "/comment?url=<tweet_url>"
    })

@app.route("/comment", methods=["GET"])
def comment():
    url = request.args.get("url")
    data, error = get_tweet_data(url)
    if error:
        return jsonify(error), 400

    tweet_text = data["data"]["text"]
    author = data["includes"]["users"][0]["username"]

    prompt = f"""Read this tweet by @{author} and write two comments (4–9 words each):
    1. Casual
    2. Smart influencer style
    Keep them natural and human, not robotic.
    Tweet: {tweet_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a witty social media commenter."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=60
        )

        reply = response.choices[0].message.content.strip()
        return jsonify({
            "tweet_text": tweet_text,
            "comments": reply
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
