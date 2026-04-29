import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Gemini 3.1 Flash", layout="wide")

# جلب المفتاح من Secrets
GEMINI_KEY = st.secrets.get("GEMINI_KEY")

# --- 2. دالة محرك Gemini 3.1 Flash ---
def process_with_gemini_3_1(file_bytes, mime_type):
    if not GEMINI_KEY:
        st.error("⚠️ مفتاح Gemini مفقود في الـ Secrets!")
        return None
    
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # تثبيت الموديل على الإصدار 3.1 فلاش
        MODEL_NAME = 'gemini-3.1-flash'
        
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        
        prompt = """
        Extract all items into a JSON object with an 'items' key. 
        Required fields for each item: hs_code, description, qty, weight, origin.
        Return ONLY valid JSON.
        """
        
        content = [
            {"mime_type": "image/jpeg", "data": file_bytes},
            prompt
        ]
        
        # تنفيذ الطلب
        response = model.generate_content(content)
        
        # تنظيف النص المستخرج لضمان استخراج JSON فقط
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response.text)

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            st.warning("⏳ تم تجاوز حد السرعة (5 طلبات/دقيقة). جاري الانتظار 10 ثوانٍ والمحاولة مرة أخرى...")
            time.sleep(10) # انتظار بسيط قبل المحاولة التلقائية
            return process_with_gemini_3_1(file_bytes, mime_type) # إعادة المحاولة مرة واحدة
        else:
            st.error(f"❌ فشل Gemini 3.1: {error_msg}")
            return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Gemini 3.1 Flash Engine")
st.info(f"المحرك النشط حالياً: Gemini 3.1 Flash (Free Tier)")

uploaded_file = st.file_uploader("ارفع المستند (صورة أو PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 تحليل البيانات"):
        with st.spinner("جاري المعالجة عبر Gemini 3.1..."):
            final_items = []
            file_bytes = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    # تحويل الصفحة لصورة بدقة 2x
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_gemini_3_1(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                    
                    # ملاحظة: إذا كان الـ PDF طويل، يفضل إضافة انتظار بسيط هنا لتجنب خطأ 429
                    if len(doc) > 1:
                        time.sleep(2) 
                doc.close()
            else:
                data = process_with_gemini_3_1(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            # عرض النتائج في جدول
            if final_items:
                st.success(f"تم استخراج {len(final_items)} أصناف بنجاح.")
                df = pd.DataFrame(final_items)
                st.data_editor(df, use_container_width=True)
            else:
                st.warning("لم يتم العثور على بيانات. يرجى التأكد من أن الملف واضح ومن صحة المفاتيح.")
