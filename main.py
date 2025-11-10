from flask import Flask, request, jsonify
import requests
import os
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route("/comment", methods=["GET"])
def comment():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing tweet URL"}), 400

    tweet_id = url.split("/")[-1]
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")

    headers = {"Authorization": f"Bearer {bearer_token}"}
    api_url = f"https://api.x.com/2/tweets/{tweet_id}?expansions=author_id&tweet.fields=created_at,text&user.fields=username"

    try:
        response = requests.get(api_url, headers=headers)
        data = response.json()

        if "data" not in data:
            return jsonify({"error": "Tweet not found or restricted", "details": data}), 400

        tweet_text = data["data"]["text"]
        author = data["includes"]["users"][0]["username"]
    except Exception as e:
        return jsonify({"error": "Tweet fetch failed", "details": str(e)}), 400

    # Generate 2 short comments (4–8 words)
    prompt = f"""
    Write 2 short, natural comments (4–8 words each) for this tweet:
    "{tweet_text}"

    Format your reply in JSON like this:
    {{
      "Casual": "<comment1>",
      "Influencer": "<comment2>"
    }}
    """

    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        comments = result.choices[0].message.content
    except Exception as e:
        return jsonify({"error": "Failed to generate comments", "details": str(e)}), 500

    return jsonify({
        "author": author,
        "tweet_text": tweet_text,
        "comments": comments
    })
