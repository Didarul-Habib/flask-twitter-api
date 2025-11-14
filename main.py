from flask import Flask, request, jsonify
from openai import OpenAI
import openai._exceptions as openai_error
import re
import time
import os

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------- Clean Tweet URL ----------
def clean_tweet_url(url):
    return re.sub(r'\?.*$', '', url.strip())


# ---------- OpenAI Retry Handler ----------
def call_openai_with_retry(payload, retries=5):
    for attempt in range(retries):
        try:
            return client.chat.completions.create(**payload)
        except openai_error.RateLimitError as e:
            wait_time = 60 * (attempt + 1)
            print(f"[429] Rate limit hit. Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
        except openai_error.APIError as e:
            print(f"[API Error] {e}. Waiting before retry...")
            time.sleep(10)
        except Exception as e:
            print(f"[Error] Attempt {attempt+1} failed: {e}")
            time.sleep(5)
    raise Exception("❌ All retry attempts failed for this batch.")


@app.route("/")
def home():
    return "✅ CrownTALK API active and stable."


@app.route("/comment", methods=["POST"])
def comment():
    try:
        data = request.get_json()
        urls = data.get("urls", [])

        if not urls or not isinstance(urls, list):
            return jsonify({"error": "Missing or invalid 'urls' list"}), 400

        # Clean & limit batch size
        urls = [clean_tweet_url(u) for u in urls if u.strip()]
        if len(urls) > 2:
            urls = urls[:2]

        formatted_output = ""
        failed_links = []
        batch_num = 1
        total_batches = 1

        print(f"Processing batch {batch_num}/{total_batches}: {urls}")

        # Build prompt
        prompt = (
            "You are CrownTALK — an AI that writes short, natural, human-like comments for tweets. "
            "Generate two comments per tweet that sound authentic and conversational. "
            "Do not use repeated patterns or overused words like 'game changer', 'finally', 'love to see', 'curious', 'excited', or 'can't wait'. "
            "Keep every comment between 4 and 10 words, no punctuation at the end, and avoid starting with the same few words. "
            "For example: 'lowkey this looks next level' or 'tbh that’s a solid move'.\n\n"
        )

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
            for url in urls:
                formatted_output += f"🔗 {url}\n{text}\n" + ("─" * 40) + "\n"

        return jsonify({
            "summary": f"✅ Completed {batch_num}/{total_batches} batch(es).",
            "failed_links": failed_links,
            "formatted": formatted_output.strip()
        }), 200

    except Exception as e:
        print(f"[Server Error] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
