# نشر الواجهة على GitHub Pages

## مهم
GitHub Pages يشغّل HTML وJavaScript فقط، ولا يشغّل `app.py`. لكي يعمل استخراج PDF بنفس الكفاءة، يجب نشر `app.py` على خدمة خادم مثل Render أو Railway أو Google Cloud Run، ثم وضع عنوانه في `github-pages-config.js`.

## ملفات GitHub Pages
ارفع هذه الملفات إلى جذر المستودع:

- `index.html`
- `github-pages-config.js`

في `github-pages-config.js` استبدل:

```js
window.PDF_API_URL = "https://YOUR-BACKEND-DOMAIN.example.com";
```

بعنوان خادمك الحقيقي، دون `/` في النهاية.

## ملفات الخادم
انشر هذه الملفات على خدمة Python:

- `app.py`
- `requirements.txt`

واضبط المتغيرات السرية في إعدادات الخادم فقط:

```text
OPENAI_API_KEY=المفتاح السري
OPENAI_API_BASE=رابط واجهة النموذج
VISION_MODEL=gemini-3.1-pro-preview
FRONTEND_ORIGIN=https://اسمك.github.io
```

لا تضع `OPENAI_API_KEY` داخل GitHub أو داخل أي ملف JavaScript.

## GitHub Pages
1. أنشئ مستودعًا عامًا باسم مناسب.
2. ارفع `index.html` و`github-pages-config.js`.
3. من `Settings → Pages` اختر `Deploy from a branch`.
4. اختر `main` ومجلد `/root`.
5. احفظ وانتظر رابط GitHub Pages.
6. ضع رابط GitHub Pages في `FRONTEND_ORIGIN` على خادم Python.

بعد ذلك ستعمل الواجهة من GitHub Pages، وسترسل PDF إلى خادم Gemini الآمن.
