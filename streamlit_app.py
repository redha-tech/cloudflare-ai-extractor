import streamlit as st
import pandas as pd
import json
import base64
import requests # سنستخدم requests لضمان توافق التنسيق
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen 3 Fixed", layout="wide", page_icon="🚢")

# استدعاء المفتاح
API_KEY = st.secrets.get("GROQ_API_KEY") 

# --- 2. دالة المعالجة المصححة للخطأ 400 ---
def process_with_qwen3_fixed(file_bytes, mime_type):
    if not API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    try:
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        # الرابط الخاص بالمنصة (تأكد إذا كان OpenRouter استخدم رابطهم)
        # إذا كنت تستخدم OpenRouter: https://openrouter.ai/api/v1/chat/completions
        # إذا كنت تستخدم Groq: https://api.groq.com/openai/v1/chat/completions
        API_URL = "https://openrouter.ai/api/v1/chat/completions" 

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        prompt = (
            "Extract items from this customs document into JSON format. "
            "Required keys: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text. Return ONLY JSON with an 'items' key."
        )

        # التنسيق الذي يحل مشكلة "must be a string" في بعض المنصات
        payload = {
            "model": "qwen/qwen3-32b",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_file}"}
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        response = requests.post(API_URL, headers=headers, json=payload)
        response_json = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ من المنصة: {response_json}")
            return None

        content = response_json['choices'][0]['message']['content']
        return json.loads(content)
        
    except Exception as e:
        st.error(f"❌ فشل المعالجة: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen 3 Engine")

uploaded_file = st.file_uploader("ارفع الملف", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 تحليل واستخراج"):
        with st.spinner("جاري التواصل مع Qwen 3..."):
            final_items = []
            
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen3_fixed(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_qwen3_fixed(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                st.success("✅ تم الاستخراج!")
                st.data_editor(df, use_container_width=True)
