import streamlit as st
import pandas as pd
import json
import fitz  # PyMuPDF
import google.generativeai as genai

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Gemini Extraction", layout="wide")

# جلب المفتاح بأمان من قسم Secrets
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("❌ مفتاح 'GEMINI_API_KEY' غير موجود في قسم Secrets. يرجى إضافته للمتابعة.")
    st.stop()

# --- 2. دالة معالجة البيانات عبر Gemini ---
def process_with_gemini(text_content):
    try:
        # استخدام Gemini 1.5 Flash كخيار تلقائي عالي الأداء
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            }
        )
        
        # الـ Prompt المخصص لاستخراج الحقول المطلوبة بدقة
        prompt = f"""
        Extract customs data from the text below into a structured JSON format.
        Focus on these specific fields:
        1. hs_code: Tariff code (e.g., 320890).
        2. origin: Country of origin (e.g., US, CN, SA).
        3. amount: The currency value/price for the line item.
        4. description: Brief product details.
        5. qty: Quantity.

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
        
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        st.error(f"⚠️ خطأ أثناء المعالجة: {str(e)}")
        return None

# --- 3. واجهة المستخدم (Streamlit UI) ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("تم ضبط النظام لاستخدام مفتاح API من الـ **Secrets** واستخراج البيانات المطلوبة.")

uploaded_file = st.file_uploader("ارفع ملف البيان الجمركي (PDF)", type=['pdf'])

if uploaded_file:
    if st.button("🚀 بدء الاستخراج"):
        with st.spinner("جاري قراءة الملف وتحليل البيانات..."):
            
            # استخراج النص من الـ PDF
            file_bytes = uploaded_file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = " ".join([page.get_text() for page in doc])
            doc.close()

            # تشغيل محرك Gemini
            result = process_with_gemini(full_text)
            
            if result and 'items' in result:
                items = result['items']
                if items:
                    st.success(f"✅ تم العثور على {len(items)} بند.")
                    
                    # عرض النتائج في جدول
                    df = pd.DataFrame(items)
                    
                    # إعادة ترتيب الأعمدة لتبرز الحقول المطلوبة أولاً
                    cols = ['hs_code', 'origin', 'amount', 'description', 'qty']
                    df = df[[c for c in cols if c in df.columns]]
                    
                    st.data_editor(df, use_container_width=True)
                    
                    # زر تحميل الملف
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 تحميل النتائج (CSV)", csv, "extracted_data.csv", "text/csv")
                else:
                    st.warning("لم يتم العثور على بيانات مطابقة.")
