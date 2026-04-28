import streamlit as st
import pandas as pd
import json
import base64
import requests
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Groq Qwen Engine", layout="wide", page_icon="🚢")

# استدعاء المفتاح (الذي يبدأ بـ gsk_)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") 

# --- 2. دالة المعالجة الخاصة بـ Groq ---
def process_with_groq_qwen(file_bytes, mime_type):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح gsk_ مفقود في Secrets!")
        return None
    
    try:
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        # الرابط الرسمي لـ Groq
        API_URL = "https://api.groq.com/openai/v1/chat/completions" 

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        # ملاحظة: في Groq، اسم الموديل لـ Qwen غالباً يكون qwen-2.5-72b أو مشابه
        # سنستخدم الموديل الأكثر استقراراً للرؤية على Groq حالياً
        MODEL_ID = "llama-3.2-11b-vision-instant" 
        
        # إذا كنت متأكداً أن Groq أضافت Qwen 3 في حسابك، استبدل الاسم أدناه بـ:
        # qwen-2.5-vl-72b (تأكد من الاسم في console.groq.com)

        prompt = (
            "Extract invoice items into JSON. Keys: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text. Return ONLY JSON with 'items' key."
        )

        payload = {
            "model": MODEL_ID,
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
        response_data = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ من Groq ({response.status_code}): {response_data.get('error', {}).get('message')}")
            return None

        content = response_data['choices'][0]['message']['content']
        return json.loads(content)
        
    except Exception as e:
        st.error(f"❌ فشل: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Groq Engine")
st.info("تم ضبط الإعدادات لتتوافق مع مفتاح Groq (gsk).")

uploaded_file = st.file_uploader("ارفع الفاتورة (PDF/Image)", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 استخراج البيانات"):
        with st.spinner("جاري المعالجة عبر Groq..."):
            final_items = []
            
            file_data = uploaded_file.read()
            
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_data, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_groq_qwen(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_groq_qwen(file_data, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.data_editor(pd.DataFrame(final_items), use_container_width=True)
