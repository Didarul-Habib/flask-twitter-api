from flask import Flask, request, jsonify
import requests
from openai import OpenAI
import re

app = Flask(__name__)
client = OpenAI()

@app.route("/")
def home():
    return jsonify({
        "message": "Server is running",
        "usage": "/comment?url=<tweet_url>"
    })

@app.route("/comment", methods=["GET"])
def comment():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing tweet URL"}), 400

    # --- Fetch tweet text using free vxTwitter API ---
    try:
        api_url = f"https://api.vxtwitter.com/{url.replace('https://', '')}"
        r = requests.get(api_url, timeout=10)
        data = r.json()

        if "text" not in data or not data["text"]:
            return jsonify({"error": "Could not fetch tweet content"}), 404

        tweet_text = data["text"]
        author = data.get("user_screen_name", "unknown")
    except Exception as e:
        return jsonify({"error": f"Failed to fetch tweet: {str(e)}"}), 500

    # --- Generate short contextual comments (4–8 words) ---
    prompt = (
        "You are a concise, natural commenter. "
        "Write two separate short comments (each 4–8 words) reacting naturally to this tweet:\n\n"
        f"Tweet: {tweet_text}\n\n"
        "Return only the two comments, separated by new lines."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        raw_output = response.choices[0].message.content.strip()

        # Extract each line as a separate comment
        comments = [re.sub(r"^\d+[\.\)]\s*", "", line).strip() 
                    for line in raw_output.splitlines() if line.strip()]
        comments = [c for c in comments if 4 <= len(c.split()) <= 8]

        if not comments:
            comments = ["Nice point!", "Interesting perspective."]

        return jsonify({
            "author": author,
            "tweet_text": tweet_text,
            "comments": comments
        })

    except Exception as e:
        return jsonify({"error": f"AI generation failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
