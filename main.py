from flask import Flask, request, jsonify
import snscrape.modules.twitter as sntwitter
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route("/comment", methods=["GET"])
def comment():
    url = request.args.get("url")

    # Step 1: Try to scrape the tweet
    try:
        tweet = next(sntwitter.TwitterTweetScraper(url).get_items())
        tweet_text = tweet.rawContent
        author = tweet.user.username
    except Exception as e:
        # Step 2: Handle scraping failure
        return jsonify({
            "error": "Could not fetch tweet content.",
            "details": str(e),
            "tweet_text": "",
            "comments": []
        }), 400

    # Step 3: Ask GPT to generate two short comments
    prompt = f"""
    Generate 2 short, natural comments (4–8 words) for this tweet:
    "{tweet_text}"

    Return them in JSON with keys: "Casual" and "Influencer".
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({
            "error": "Failed to generate comments.",
            "details": str(e)
        }), 500

    # Step 4: Return final structured response
    return jsonify({
        "author": author,
        "tweet_text": tweet_text,
        "comments": text
    })
