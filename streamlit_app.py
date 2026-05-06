import streamlit as st
import pandas as pd
import json
import fitz  # PyMuPDF
import re
import time
from groq import Groq

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Groq Llama 3.1 Optimized", layout="wide")

# جلب المفتاح من Secrets
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة محرك Groq المتقدمة ---
def process_with_groq_llama(text_content):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح Groq مفقود في الـ Secrets!")
        return None
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # استخدام موديل 8B Instant لقدرته العالية على تحمل التوكنز والسرعة
        MODEL_NAME = 'llama-3.1-8b-instant'
        
        # الـ Prompt مع إضافة مرحلة تحليل الهيكل (Identify Table Structure)
        system_prompt = """
        You are an expert Customs Declaration Data Extractor. 
        Before extracting, first IDENTIFY THE TABLE STRUCTURE: 
        1. Locate where the headers like 'H.S. CODE', 'Description', 'Weight', and 'QTY' are positioned.
        2. Recognize that the document may have a multi-column or row-based layout.
        
        STRICT EXTRACTION RULES:
        1. Identification: Each item starts with a valid H.S. CODE (e.g., 320890909999).
        2. Merging: If multiple rows belong to the same item/HS code, merge them into ONE single entry.
        3. Exclusion: Do NOT extract company names (GULF AGENCY, etc.), customs point names, or footer/header info as line items.
        4. Data Fields:
           - hs_code: The 8-12 digit tariff code.
           - description: Full product description (exclude company names).
           - qty: Quantity (look specifically for the 'QTY' or 'الكمية' column).
           - weight: Net/Gross weight values (e.g., 28.00).
           - origin: Country code (e.g., 'US', 'GB').
           - amount: Total currency value for that specific item.

        Return ONLY a valid JSON object. Do not include any reasoning or conversational text.
        """
        
        user_content = f"ANALYZE STRUCTURE AND EXTRACT ITEMS FROM THIS TEXT:\n{text_content}"
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},
            temperature=0.1  # بقاء القيمة منخفضة لضمان الدقة
        )
        
        return json.loads(chat_completion.choices[0].message.content)

    except Exception as e:
        st.error(f"❌ Groq Error: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Customs Data Extractor")
st.info("المحرك الحالي مدعوم بميزة: Identify Table Structure لزيادة الدقة")
st.markdown("---")

uploaded_file = st.file_uploader("ارفع البيان الجمركي (PDF)", type=['pdf'])

if uploaded_file:
    if st.button("🚀 بدء التحليل الذكي"):
        with st.spinner("جاري تحليل هيكل المستند واستخراج البيانات..."):
            
            # قراءة الملف
            file_bytes = uploaded_file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            # استخراج النص من كافة الصفحات
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()

            # معالجة النص عبر Groq
            result = process_with_groq_llama(full_text)
            
            if result and 'items' in result:
                items = result['items']
                
                if items:
                    st.success(f"✅ تم استخراج {len(items)} بند بنجاح.")
                    
                    # تحويل لجدول
                    df = pd.DataFrame(items)
                    
                    # التأكد من ترتيب الأعمدة المطلوبة
                    cols_order = ['hs_code', 'description', 'qty', 'weight', 'origin', 'amount']
                    actual_cols = [c for c in cols_order if c in df.columns]
                    
                    # عرض الجدول التفاعلي
                    st.data_editor(df[actual_cols], use_container_width=True, num_rows="dynamic")
                    
                    # خيار تحميل البيانات
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 تحميل النتائج (CSV)", csv, "extracted_items.csv", "text/csv")
                else:
                    st.warning("⚠️ لم يتم العثور على بنود واضحة. قد يكون الهيكل غير مألوف.")
            else:
                st.error("⚠️ فشل في تحليل هيكل البيانات.")

# إرشادات للمستخدم
with st.sidebar:
    st.header("تعليمات الاستخدام")
    st.info("""
    - ميزة 'Table Structure Identification' تساعد في فهم الفواتير ذات الأعمدة المتداخلة.
    - المحرك يتجاهل تلقائياً ترويسة الصفحة ويركز على جداول البضائع.
    """)
