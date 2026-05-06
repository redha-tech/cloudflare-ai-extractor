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
        
        # Prompt محسّن لمنع التكرار ومعالجة بيانات الجمارك (Bahrain Customs Specific)
        system_prompt = """
        You are an expert Customs Declaration Data Extractor. 
        Your goal is to extract ONLY the line items (goods) listed in the declaration.
        
        STRICT RULES:
        1. Identification: Each item starts with an H.S. CODE (e.g., 320890909999). 
        2. Merging: If multiple lines refer to the same H.S. Code and description, merge them into ONE item.
        3. Exclusion: Do NOT extract names of companies (GULF AGENCY, etc.), customs points, or header info as items.
        4. Data Fields:
           - hs_code: The 8-12 digit tariff code.
           - description: The goods description (e.g., 'Other', 'Paint', etc.).
           - qty: The quantity (found near the 'QTY' or 'الكمية' labels).
           - weight: The Net/Gross weight (found near '28.00' or similar values).
           - origin: The country code (e.g., 'US', 'China').
           - amount: The total value in foreign or local currency.

        Return ONLY a valid JSON object. No conversational text.
        """
        
        user_content = f"EXTRACT ITEMS FROM THIS TEXT:\n{text_content}"
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},
            temperature=0.1  # تقليل العشوائية لضمان دقة الأرقام
        )
        
        return json.loads(chat_completion.choices[0].message.content)

    except Exception as e:
        st.error(f"❌ Groq Error: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Customs Data Extractor")
st.markdown("---")

uploaded_file = st.file_uploader("ارفع البيان الجمركي (PDF)", type=['pdf'])

if uploaded_file:
    if st.button("🚀 بدء التحليل الذكي"):
        with st.spinner("جاري قراءة البيانات وتحليلها..."):
            
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
                    st.warning("⚠️ لم يتم العثور على بنود واضحة في المستند.")
            else:
                st.error("⚠️ فشل في تحليل هيكل البيانات.")

# إرشادات للمستخدم
with st.sidebar:
    st.header("تعليمات الاستخدام")
    st.info("""
    - يفضل رفع ملفات PDF الأصلية (Digital) للحصول على أعلى دقة.
    - المحرك مصمم حالياً للتعرف على بيانات الجمارك (H.S. Code).
    - إذا واجهت خطأ في التوكنز، حاول رفع صفحات أقل.
    """)
