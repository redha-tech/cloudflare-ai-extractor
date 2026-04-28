import streamlit as st
import pandas as pd
import json
import base64
import requests
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Dedicated", layout="wide", page_icon="🚢")

# استلام المفتاح الذي يبدأ بـ gsk_
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة لجلب اسم موديل Qwen المتاح حالياً في Groq ---
def get_qwen_model_name():
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        # جلب قائمة الموديلات المتاحة لمفتاحك من سيرفر Groq
        response = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
        if response.status_code == 200:
            models = response.json().get('data', [])
            # البحث عن أي موديل يحتوي على كلمة Qwen
            qwen_models = [m['id'] for m in models if "qwen" in m['id'].lower()]
            if qwen_models:
                # ترتيب لاختيار الأحدث أو الأكبر (مثل qwen-2.5-72b)
                qwen_models.sort(reverse=True)
                return qwen_models[0]
        return None
    except:
        return None

# --- 3. دالة المعالجة الأساسية ---
def process_with_qwen(file_bytes, mime_type):
    target_model = get_qwen_model_name()
    
    if not target_model:
        st.error("❌ لم يتم العثور على موديل Qwen في حسابك. تأكد من تفعيله في Groq Console.")
        return None

    try:
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        # رابط API الخاص بـ Groq
        API_URL = "https://api.groq.com/openai/v1/chat/completions" 

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": target_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract items from this invoice into JSON. Required fields: hs_code, description, qty, weight, origin. Keep Arabic. Return ONLY JSON with 'items' key."
                        },
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
        res_data = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ من Groq: {res_data.get('error', {}).get('message')}")
            return None

        return json.loads(res_data['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"❌ فشل المعالجة: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen Vision Engine")
st.info("تم ضبط المحرك للبحث عن موديلات Qwen المتاحة لمفتاحك (gsk).")

uploaded_file = st.file_uploader("ارفع الفاتورة (PDF/Image)", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 استخراج البيانات بواسطة Qwen"):
        with st.spinner("جاري الاتصال بمحرك Qwen..."):
            final_items = []
            file_data = uploaded_file.read()
            
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_data, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_qwen(file_data, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success("✅ تم الاستخراج بنجاح!")
                st.data_editor(pd.DataFrame(final_items), use_container_width=True)
