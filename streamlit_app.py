import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Vision Fix", layout="wide")

API_KEY = st.secrets.get("OPENROUTER_API_KEY")

def process_with_vision(file_bytes, mime_type):
    if not API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        API_URL = "https://openrouter.ai/api/v1/chat/completions"
        
        # تغيير الموديل لضمان وجود Endpoint نشط
        # سنستخدم النسخة المستقرة التي تدعم الرؤية دائماً
        MODEL_ID = "qwen/qwen-2-vl-72b-instruct" 

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract all items into a JSON object. Required fields: hs_code, description, qty, weight, origin. Return ONLY JSON with an 'items' key."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2000
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
        res_json = response.json()

        if response.status_code != 200:
            # إذا فشل Qwen، سنقوم بالتحويل التلقائي لموديل رؤية بديل ومجاني أحياناً لضمان العمل
            st.warning(f"الموديل {MODEL_ID} غير متاح حالياً، جاري المحاولة عبر محرك احتياطي...")
            payload["model"] = "google/gemini-flash-1.5" # موديل احتياطي قوي جداً في الرؤية
            response = requests.post(API_URL, headers=headers, json=payload)
            res_json = response.json()

        content = res_json['choices'][0]['message']['content']
        return json.loads(content)

    except Exception as e:
        st.error(f"❌ فشل المحرك: {str(e)}")
        return None

# --- الواجهة ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 استخراج البيانات"):
        with st.spinner("جاري المعالجة..."):
            final_items = []
            file_bytes = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    # رفع الدقة قليلاً لضمان رؤية البيانات (Matrix 2.0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_vision(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_vision(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.data_editor(pd.DataFrame(final_items), use_container_width=True)
            else:
                st.warning("لم يتم العثور على بيانات. تأكد من وضوح المستند.")
