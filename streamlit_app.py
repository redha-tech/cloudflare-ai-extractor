import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
import tempfile
import os
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Vision Test | Gemini 3.1 Lite", layout="wide")

# جلب المفتاح بأمان
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("❌ مفتاح 'GEMINI_API_KEY' غير موجود في قسم Secrets.")
    st.stop()

# --- 2. دالة المعالجة عبر Vision ---
def process_vision(file_path, mime_type):
    try:
        target_model = 'models/gemini-3.1-flash-lite'
        
        # 1. رفع الملف إلى Google
        st.info("⬆️ جاري رفع الملف لمعالجته بتقنية Vision...")
        uploaded_file = genai.upload_file(path=file_path, mime_type=mime_type)
        
        # الانتظار حتى اكتمال المعالجة
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        # 2. إعداد الموديل
        model = genai.GenerativeModel(
            model_name=target_model,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            }
        )
        
        prompt = """
        Analyze this document image/PDF and extract customs data into JSON.
        Required fields: hs_code, origin, amount, description, qty.
        Return format: {"items": [{"hs_code": "...", "origin": "...", "amount": "...", "description": "...", "qty": "..."}]}
        """
        
        st.info(f"🔄 جاري التحليل باستخدام: {target_model}")
        response = model.generate_content([uploaded_file, prompt])
        
        # تنظيف الملف من السحابة بعد المعالجة
        genai.delete_file(uploaded_file.name)
        
        return json.loads(response.text)

    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة Vision: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("📸 اختبار Vision: Gemini 3.1 Flash Lite")

uploaded_file = st.file_uploader("ارفع ملف (PDF أو صورة)", type=['pdf', 'jpg', 'png', 'jpeg'])

if uploaded_file:
    if st.button("🚀 بدء تحليل Vision"):
        with st.spinner("جاري المعالجة..."):
            # حفظ الملف مؤقتاً لرفعه
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            try:
                result = process_vision(tmp_path, uploaded_file.type)
                
                if result and 'items' in result:
                    st.success(f"✅ نجحت Vision! تم استخراج {len(result['items'])} بند.")
                    st.table(pd.DataFrame(result['items']))
                else:
                    st.warning("لم يتم إرجاع بيانات JSON صحيحة.")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
