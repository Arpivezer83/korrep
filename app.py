from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from openai import OpenAI
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# Rate limiter based on IP
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"]
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Session control
SESSION_TIMEOUT = 60 * 60  # 60 minutes
MAX_COST = 5.0  # USD
MODEL_COST_PER_1K_TOKENS = 0.005  # conservative estimate (GPT-4o)

# System prompt template
SYSTEM_PROMPT = """
Te egy kedves, türelmes magántanár vagy, aki egy 10 éves gyermeket tanít. Mindig dicsérsz, segítőkészen válaszolsz, és ha a gyerek nem tud valamit, bátorítod. A cél, hogy örömmel tanuljon veled.
"""

@app.route("/korrep", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("KORREP_PASSWORD", "panni2025"):
            session["logged_in"] = True
            session["start_time"] = time.time()
            session["total_tokens"] = 0
            return redirect(url_for("chat"))
        else:
            return render_template("login.html", error="Hibás jelszó.")
    return render_template("login.html")

@app.route("/korrep/chat")
def chat():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("chat.html")

@app.route("/korrep/api/message", methods=["POST"])
def message():
    if not session.get("logged_in"):
        return jsonify({"error": "Nincs belépve."}), 403

    # Check time limit
    elapsed = time.time() - session.get("start_time", time.time())
    if elapsed > SESSION_TIMEOUT:
        return jsonify({"error": "Az idő lejárt. A tanóra véget ért."}), 403

    data = request.json
    user_message = data.get("message", "")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        reply = response.choices[0].message.content
        total_tokens = response.usage.total_tokens

        # Cost control
        session["total_tokens"] += total_tokens
        estimated_cost = session["total_tokens"] / 1000 * MODEL_COST_PER_1K_TOKENS

        if estimated_cost > MAX_COST:
            return jsonify({"error": "Elérted a maximális keretet. A tanóra véget ért."}), 403

        return jsonify({"reply": reply})

    except Exception as e:
        import traceback
        print("❌ Hiba történt:")
        traceback.print_exc()
        return jsonify({"error": "Belső hiba: " + str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
