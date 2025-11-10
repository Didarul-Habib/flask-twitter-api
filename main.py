import requests
from flask import Flask, jsonify, request
import re
import os

app = Flask(__name__)

# Bearer Token stored as environment variable
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

def extract_tweet_id(url):
    match = re.search(r"status/(\d+)", url)
    return match.group(1) if match else None

@app.route("/")
def home():
    return jsonify({"message": "Server is running", "usage": "/gettweet?url=<tweet_url>"})

@app.route("/gettweet", methods=["GET"])
def get_tweet():
    url = request.args.get("url")
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return jsonify({"error": "Invalid tweet URL"}), 400

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    api_url = f"https://api.x.com/2/tweets/{tweet_id}?expansions=author_id&tweet.fields=created_at,text&user.fields=username"

    try:
        response = requests.get(api_url, headers=headers)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
