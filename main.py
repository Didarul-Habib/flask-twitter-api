from flask import Flask, jsonify, request
import snscrape.modules.twitter as s
import re

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "message": "Server is running",
        "usage": "/gettweet?url=<tweet_url>"
    })


def extract_tweet_id(url):
    match = re.search(r"status/(\d+)", url)
    return match.group(1) if match else None


@app.route("/gettweet", methods=["GET"])
def get_tweet():
    url = request.args.get("url")
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return jsonify({"error": "Invalid tweet URL"}), 400

    try:
        full_url = f"https://x.com/i/web/status/{tweet_id}"
        scraper = s.TwitterTweetScraper(full_url)
        tweet = next(scraper.get_items(), None)
        if tweet:
            return jsonify({
                "tweet_id": tweet.id,
                "username": tweet.user.username,
                "content": tweet.content
            })
        return jsonify({"error": "Tweet not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
