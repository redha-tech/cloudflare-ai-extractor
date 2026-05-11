import streamlit as st
import pandas as pd
import json
import fitz  # PyMuPDF
import google.generativeai as genai

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Test Env | Gemini 3.1 Lite", layout="wide")

# جلب المفتاح بأمان من قسم Secrets
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("❌ مفتاح 'GEMINI_API_KEY' غير موجود في قسم Secrets.")
    st.stop()

# --- 2. دالة معالجة البيانات عبر Gemini 3.1 Lite ---
def process_with_gemini(text_content):
    try:
        # التعديل هنا: استخدام الموديل 3.1 Lite حصراً للاختبار
        target_model = 'models/gemini-3.1-flash-lite'
        
        model = genai.GenerativeModel(
            model_name=target_model,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            }
        )
        
        prompt = f"""
        Extract customs data from the text below into a structured JSON format.
        Focus on these specific fields:
        1. hs_code, 2. origin, 3. amount, 4. description, 5. qty.

        Return JSON in this format:
        {{
          "items": [
            {{
              "hs_code": "...",
              "origin": "...",
              "amount": "...",
              "description": "...",
              "qty": "..."
            }}
          ]
        }}

        TEXT:
        {text_content}
        """
        
        st.info(f"🔄 جاري المحاولة باستخدام: {target_model}")
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        st.error(f"⚠️ خطأ في موديل 3.1 Lite: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🧪 بيئة اختبار: Gemini 3.1 Flash Lite")
st.markdown(f"هذا المشروع مخصص لاختبار استجابة الموديل الجديد فقط.")

uploaded_file = st.file_uploader("ارفع ملف PDF للتجربة", type=['pdf'])

if uploaded_file:
    if st.button("🚀 بدء اختبار الاستخراج"):
        with st.spinner("جاري التحليل..."):
            
            # استخراج النص
            file_bytes = uploaded_file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = " ".join([page.get_text() for page in doc])
            doc.close()

            # تشغيل الموديل
            result = process_with_gemini(full_text)
            
            if result and 'items' in result:
                items = result['items']
                st.success(f"✅ نجح الاستخراج! تم العثور على {len(items)} بند.")
                df = pd.DataFrame(items)
                st.table(df) # استخدام table بدلاً من dataframe للتأكد من العرض البسيط
            else:
                st.warning("فشل الموديل في إرجاع بيانات JSON صحيحة.")
