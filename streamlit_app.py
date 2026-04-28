import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Vision Dedicated", layout="wide", page_icon="🚢")

# المفتاح الخاص بك (الذي يبدأ بـ gsk_)
API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة المعالجة باستخدام Qwen Vision حصراً ---
def process_with_qwen_vision(file_bytes, mime_type):
    if not API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    try:
        # تحويل الصورة إلى Base64
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        # الرابط الرسمي لـ Groq
        API_URL = "https://api.groq.com/openai/v1/chat/completions"
        
        # ملاحظة هامة: يجب أن يكون الموديل يدعم Vision (VL)
        # إذا لم يعمل هذا الاسم، تأكد من الاسم الدقيق في Console Groq (مثل qwen-2.5-vl-72b)
        MODEL_ID = "qwen-2.5-vl-72b" 

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        # الهيكل الصحيح لإرسال الصور لـ Qwen على Groq
        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract all items from this document into a JSON format. Required fields: hs_code, description, qty, weight, origin. Ensure Arabic text is preserved. Return ONLY JSON with 'items' key."
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
            "response_format": {"type": "json_object"},
            "temperature": 0.1 # لزيادة الدقة في الأرقام
        }

        response = requests.post(API_URL, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown Error')
            # إذا كان الخطأ متعلقاً بعدم وجود الموديل، سنخبر المستخدم بالبحث عن الاسم الصحيح
            if "does not exist" in error_msg:
                st.error(f"❌ الموديل {MODEL_ID} غير متاح في حسابك. يرجى التأكد من اسم موديل Qwen Vision المتاح لك في Groq Console.")
            else:
                st.error(f"❌ خطأ من Groq: {error_msg}")
            return None

        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)

    except Exception as e:
        st.error(f"❌ فشل الاتصال: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | محرك Qwen للرؤية")
st.info("هذا الإصدار مخصص لاستخدام Qwen Vision بمفتاح Groq (gsk).")

uploaded_file = st.file_uploader("ارفع الفاتورة أو بوليصة الشحن", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 استخراج البيانات (Qwen Vision)"):
        with st.spinner("جاري قراءة الصور وتحليل البيانات عبر Qwen..."):
            final_items = []
            file_bytes = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                # تحويل كل صفحة PDF إلى صورة لأن Qwen Vision يحتاج صور
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen_vision(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                # معالجة الصورة المباشرة
                data = process_with_qwen_vision(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success(f"✅ تم الاستخراج بنجاح!")
                df = pd.DataFrame(final_items)
                st.data_editor(df, use_container_width=True)
