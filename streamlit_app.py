import streamlit as st
import pandas as pd
import json
import fitz  # PyMuPDF
import re
import time
from groq import Groq

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Groq Llama 3.1", layout="wide")

# جلب المفاتيح من Secrets (تأكد من تسمية المفتاح GROQ_API_KEY في الإعدادات)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة محرك Groq Llama 3.1 8B ---
def process_with_groq_llama(text_content):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح Groq مفقود في الـ Secrets!")
        return None
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # استخدام موديل 8B Instant لضمان السرعة وتجنب الـ Rate Limit
        MODEL_NAME = 'llama-3.1-8b-instant'
        
        prompt = f"""
        Analyze the following text extracted from a document and extract all items into a JSON object with an 'items' key.
        Required fields for each item: 
        - hs_code
        - description
        - qty
        - weight
        - origin
        - amount (if available)

        Text Data:
        {text_content}

        Return ONLY a valid JSON object. Do not include any explanation.
        """
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"}
        )
        
        result = chat_completion.choices[0].message.content
        return json.loads(result)

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            st.warning("⏳ تم تجاوز حد السرعة. جاري الانتظار قليلاً...")
            time.sleep(5)
            return None
        else:
            st.error(f"❌ فشل Groq: {error_msg}")
            return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Groq Llama 3.1 Engine")
st.info(f"المحرك النشط حالياً: Llama 3.1 8B Instant (Fast Extraction)")

uploaded_file = st.file_uploader("ارفع المستند (صورة أو PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 تحليل البيانات"):
        with st.spinner("جاري المعالجة عبر Groq..."):
            final_items = []
            
            if uploaded_file.type == "application/pdf":
                file_bytes = uploaded_file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                full_text = ""
                
                # استخراج النصوص من كل صفحة بدلاً من الصور لأن Groq يعالج النصوص ببراعة
                for page in doc:
                    full_text += page.get_text() + "\n--- Page Break ---\n"
                
                data = process_with_groq_llama(full_text)
                if data and 'items' in data:
                    final_items.extend(data['items'])
                doc.close()
            else:
                # في حال رفع صورة، نحتاج لاستخراج النص منها أولاً أو إرسال الوصف (OCR بسيط)
                # ملاحظة: Groq موديل نصي، لذا يفضل رفع ملفات PDF مقروءة للحصول على أفضل نتائج
                st.warning("⚠️ محرك Groq الحالي يعمل بشكل أفضل مع ملفات PDF التي تحتوي على نصوص.")
                # هنا يمكن إضافة مكتبة مثل pytesseract إذا كانت الصور ضرورية

            # عرض النتائج في جدول
            if final_items:
                st.success(f"تم استخراج {len(final_items)} أصناف بنجاح.")
                df = pd.DataFrame(final_items)
                
                # ترتيب الأعمدة للعرض
                cols = ['hs_code', 'description', 'qty', 'weight', 'origin', 'amount']
                available_cols = [c for c in cols if c in df.columns]
                
                st.data_editor(df[available_cols], use_container_width=True)
            else:
                st.warning("لم يتم العثور على بيانات أو المجلد فارغ.")
