import streamlit as st
import pandas as pd
import json
import base64
import requests
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Vision Pro", layout="wide", page_icon="🚢")

# ضع مفتاحك الجديد هنا في Secrets باسم OPENROUTER_API_KEY
API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- 2. محرك المعالجة (OpenRouter Engine) ---
def process_with_qwen_vision(file_bytes, mime_type):
    if not API_KEY:
        st.error("⚠️ مفتاح OpenRouter مفقود في Secrets!")
        return None
    
    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        # رابط OpenRouter الرسمي
        API_URL = "https://openrouter.ai/api/v1/chat/completions"
        
        # اختيار أقوى موديل رؤية من Qwen متاح حالياً
        MODEL_ID = "qwen/qwen-2.5-vl-72b-instruct" 

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://clik-plus.streamlit.app", # اختياري لـ OpenRouter
            "X-Title": "Clik-Plus Customs Engine"
        }

        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract all items into JSON format. Keys: hs_code, description, qty, weight, origin. Keep Arabic text. Return ONLY valid JSON with 'items' key."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        res_json = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ من OpenRouter: {res_json.get('error', {}).get('message', 'Unknown Error')}")
            return None

        content = res_json['choices'][0]['message']['content']
        return json.loads(content)

    except Exception as e:
        st.error(f"❌ فشل الاتصال بالمحرك: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen 2.5 Vision")
st.markdown("تم تفعيل محرك الرؤية عبر **OpenRouter**.")

uploaded_file = st.file_uploader("ارفع الفاتورة أو بوليصة الشحن", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 تحليل المستند (Qwen-VL)"):
        with st.spinner("جاري 'رؤية' المستند واستخراج الجداول..."):
            final_items = []
            file_bytes = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                # تحويل صفحات الـ PDF لصور لضمان تفعيل خاصية الرؤية
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen_vision(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_qwen_vision(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success("✅ تم الاستخراج بنجاح!")
                df = pd.DataFrame(final_items)
                st.data_editor(df, use_container_width=True)
                
                # خيار التحميل
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 تحميل النتائج CSV", csv, "extracted_data.csv", "text/csv")
