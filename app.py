from flask import Flask, render_template, request, jsonify
from gpt_handler import get_response

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    # document = data.get("document")
    # text = pdf2Text

    user_message = data.get("message", "")

    try:
        gpt_reply = get_response(user_message)
        return jsonify({"reply": gpt_reply})
    except Exception as e:
        print("Error in /chat route:", e)
        return jsonify({"reply": "Server error occurred."}), 500

if __name__ == "__main__":
    app.run(debug=True)