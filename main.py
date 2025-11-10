import os
import re
import requests
from flask import Flask, jsonify, request
from openai import OpenAI

app = Flask(__name__)

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
    return jsonify({"message": "Server is running", "usage": "/summarize?url=<tweet_url>"})


@app.route("/summarize", methods=["GET"])
def summarize():
    url = request.args.get("url")
    data, error = get_tweet_data(url)
    if error:
        return jsonify(error), 400

    tweet_text = data["data"]["text"]
    author = data["includes"]["users"][0]["username"]

    prompt = f"Summarize this tweet by @{author} in one short sentence:\n\n{tweet_text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You summarize tweets clearly and briefly."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.5
        )
        summary = response.choices[0].message.content.strip()

        return jsonify({
            "tweet_text": tweet_text,
            "summary": summary,
            "author": author
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
