from flask import Flask, request, jsonify
from openai import OpenAI, error as openai_error
import re
import time
import os
import random

app = Flask(__name__)

# Initialize client (no proxies arg — fixes that render error)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Utility: clean tweet URLs (remove query params)
def clean_tweet_url(url):
    return re.sub(r'\?.*$', '', url.strip())

# Utility: exponential backoff handler for API calls
def call_openai_with_retry(payload, retries=5):
    for attempt in range(retries):
        try:
            return client.chat.completions.create(**payload)
        except openai_error.RateLimitError as e:
            wait_time = 60 * (attempt + 1)
            print(f"[RateLimit] Hit limit. Waiting {wait_time}s before retry ({attempt+1}/{retries})...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"[Error] Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    raise Exception("❌ All retry attempts failed for this batch.")

@app.route('/')
def home():
    return "✅ CrownTALK Comment Generator API is live."

@app.route('/comment', methods=['POST'])
def comment():
    try:
        data = request.get_json()
        urls = data.get("urls", [])

        if not urls or not isinstance(urls, list):
            return jsonify({"error": "Missing or invalid 'urls' field"}), 400

        # Clean and limit to safe batch size
        urls = [clean_tweet_url(u) for u in urls if u.strip()]
        if len(urls) > 2:
            urls = urls[:2]  # Should never happen, but just in case

        formatted_output = ""
        failed_links = []
        batch_num = 1
        total_batches = 1  # Only one batch per call now

        print(f"Processing batch {batch_num}/{total_batches}: {urls}")

        prompt = (
            "You are CrownTALK — an AI that writes short, engaging, human-style comments for tweets. "
            "For each tweet link provided, generate two unique replies that sound natural, avoid repetition, "
            "and match the tone of casual X (Twitter) engagement. Use friendly emojis where suitable, but not every line. "
            "Skip phrases like 'game changer' or 'can’t wait to see'. Keep it fresh and varied.\n\n"
        )

        # Add tweet URLs to prompt
        for url in urls:
            prompt += f"Tweet: {url}\nComments:\n"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 300
        }

        try:
            response = call_openai_with_retry(payload)
        except Exception as e:
            print(f"[Fallback Triggered] {e}")
            try:
                payload["model"] = "gpt-3.5-turbo"
                response = call_openai_with_retry(payload)
            except Exception as e2:
                print(f"[Final Fail] {e2}")
                failed_links.extend(urls)
                return jsonify({
                    "summary": f"❌ All attempts failed for {len(urls)} tweets.",
                    "failed_links": failed_links,
                    "formatted": formatted_output
                }), 500

        if response and response.choices:
            text = response.choices[0].message.content.strip()
            formatted_output += "\n\n".join([
                f"🔗 {url}\n{text.split('Tweet: ')[-1].strip()}\n" for url in urls
            ])

        return jsonify({
            "summary": f"✅ Completed {batch_num}/{total_batches} batch(es).",
            "failed_links": failed_links,
            "formatted": formatted_output
        }), 200

    except Exception as e:
        print(f"[Server Error] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
