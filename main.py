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
