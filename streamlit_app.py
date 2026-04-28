import streamlit as st
import pandas as pd
import json
import base64
import requests
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Groq Auto-Model", layout="wide", page_icon="🚢")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") 

# --- 2. دالة جلب الموديل المتاح حالياً في حسابك ---
def get_active_model_id():
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        # جلب قائمة الموديلات المتاحة لمفتاحك
        response = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
        if response.status_code == 200:
            models = response.json().get('data', [])
            # البحث عن Qwen أولاً كما طلبت
            for m in models:
                if "qwen" in m['id'].lower() and ("vl" in m['id'].lower() or "vision" in m['id'].lower()):
                    return m['id']
            # إذا لم يجد Qwen Vision، يبحث عن أي موديل Vision آخر متاح (Llama مثلاً)
            for m in models:
                if "vision" in m['id'].lower():
                    return m['id']
        return "llama-3.2-11b-vision-preview" # كخيار أخير جداً
    except:
        return "llama-3.2-11b-vision-preview"

# --- 3. دالة المعالجة ---
def process_data(file_bytes, mime_type):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    selected_model = get_active_model_id()
    # st.write(f"🔍 الموديل المستخدم حالياً: {selected_model}") # إلغاء التعليق للتأكد من الموديل

    try:
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        API_URL = "https://api.groq.com/openai/v1/chat/completions" 

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract invoice items into JSON. Keys: hs_code, description, qty, weight, origin, invoice_number. Keep Arabic. Return ONLY JSON with 'items' key."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_file}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        response = requests.post(API_URL, headers=headers, json=payload)
        res_json = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ {response.status_code}: {res_json.get('error', {}).get('message')}")
            return None

        return json.loads(res_json['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"❌ فشل: {str(e)}")
        return None

# --- 4. الواجهة ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع المستند", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 استخراج البيانات"):
        with st.spinner("جاري تحليل البيانات..."):
            final_items = []
            file_data = uploaded_file.read()
            
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_data, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_data(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_data(file_data, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.data_editor(pd.DataFrame(final_items), use_container_width=True)
