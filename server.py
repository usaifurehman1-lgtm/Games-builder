from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__)
CORS(app)

# آپ کی ای میل اور پاسورڈ یہاں ہارڈ کوڈ کر دیے گئے ہیں
USER_EMAIL = "urehmansaif2@gmail.com"
USER_PASS = "factfk8pd"

@app.route('/api/deep-search', methods=['POST'])
def deep_search():
    data = request.json
    login_url = data.get('login_url')  # جس ویب سائٹ پر لاگ ان کرنا ہے اس کا URL
    query = data.get('query', '')      # جو سرچ کرنا ہے

    try:
        with sync_playwright() as p:
            # ایک چھپا ہوا براؤزر کھولیں
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. ہدف ویب سائٹ کے لاگ ان پیج پر جائیں
            page.goto(login_url)

            # 2. ای میل اور پاسورڈ کے خانوں میں خودکار طریقے سے لکھیں
            page.fill("input[name='email'], input[type='email'], input[name='username']", USER_EMAIL)
            page.fill("input[name='password'], input[type='password']", USER_PASS)

            # 3. لاگ ان بٹن پر کلک کریں
            page.click("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
            
            # لاگ ان ہونے کا انتظار (3 سیکنڈ)
            page.wait_for_timeout(3000)

            # 4. لاگ ان کے بعد پیج کا مواد حاصل کریں یا سرچ کریں
            content = page.inner_text("body")

            browser.close()

            return jsonify({
                "status": "success",
                "result": content[:1500]  # ابتدائی 1500 الفاظ کا نتیجہ
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
