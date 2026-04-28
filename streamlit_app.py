import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Auto-Vision", layout="wide", page_icon="🚢")

# المفتاح الذي يبدأ بـ gsk_
API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة جلب موديل Qwen Vision المتاح حالياً في حسابك ---
def find_live_qwen_vision_model():
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        # جلب قائمة الموديلات التي يراها مفتاحك حالياً
        response = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
        if response.status_code == 200:
            models = response.json().get('data', [])
            # البحث عن موديل يحتوي على qwen و vl أو vision
            for m in models:
                model_id = m['id'].lower()
                if "qwen" in model_id and ("vl" in model_id or "vision" in model_id):
                    return m['id']
            
            # إذا لم يجد VL، سيبحث عن أي موديل Qwen متاح كخيار ثانوي
            for m in models:
                if "qwen" in m['id'].lower():
                    return m['id']
        return None
    except Exception as e:
        st.error(f"خطأ في الاتصال بالقائمة: {str(e)}")
        return None

# --- 3. محرك المعالجة (Vision Engine) ---
def process_file_with_qwen(file_bytes, mime_type):
    target_model = find_live_qwen_vision_model()
    
    if not target_model:
        st.error("❌ لم يتم العثور على أي موديل Qwen في حسابك على Groq. تأكد من تفعيله.")
        return None

    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        API_URL = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        # هيكلة الرسالة بما يتوافق مع موديلات الرؤية
        payload = {
            "model": target_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract all items into JSON: hs_code, description, qty, weight, origin. Return ONLY JSON with an 'items' key."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        response = requests.post(API_URL, headers=headers, json=payload)
        res_json = response.json()

        if response.status_code != 200:
            st.error(f"❌ خطأ ({target_model}): {res_json.get('error', {}).get('message')}")
            return None

        return json.loads(res_json['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"❌ فشل المحرك: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen Vision Pro")
st.markdown("استخراج البيانات الجمركية باستخدام نموذج **Qwen** المتاح في حسابك.")

uploaded_file = st.file_uploader("ارفع الفاتورة أو المستند", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 بدء تحليل Qwen"):
        with st.spinner("جاري فحص الموديلات النشطة وتحليل المستند..."):
            final_items = []
            file_content = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                # تحويل كل صفحة PDF لصورة لأن Qwen Vision يحتاج صوراً
                doc = fitz.open(stream=file_content, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_file_with_qwen(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                # معالجة الصور
                data = process_file_with_qwen(file_content, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success("✅ اكتمل الاستخراج!")
                df = pd.DataFrame(final_items)
                st.data_editor(df, use_container_width=True)
