import streamlit as st
import pandas as pd
import json
import fitz  # PyMuPDF
import google.generativeai as genai

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Gemini Optimized", layout="wide")

# جلب المفتاح من Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 2. إعداد محرك Gemini ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    st.error("⚠️ مفتاح Gemini API مفقود في الـ Secrets!")

def process_with_gemini(text_content):
    try:
        # استخدام موديل Gemini 1.5 Pro للحصول على أعلى مستوى من الدقة (أو Flash للسرعة)
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash', # يمكنك تغييره لـ gemini-1.5-pro للدقة القصوى
            generation_config={
                "temperature": 0.1,
                "top_p": 0.95,
                "response_mime_type": "application/json",
            }
        )
        
        prompt = f"""
        You are an expert Customs Declaration Data Extractor. 
        Analyze the following customs document text and extract all line items into a JSON format.
        
        STRICT EXTRACTION RULES:
        1. hs_code: Extract the tariff code (8-12 digits).
        2. origin: Extract the country of origin (e.g., 'US', 'China', 'GB').
        3. amount: Extract the total value or price for the item.
        4. description: Full product description.
        5. qty: Quantity of the item.
        6. weight: Net or Gross weight.

        JSON structure should be:
        {{
          "items": [
            {{
              "hs_code": "...",
              "description": "...",
              "qty": "...",
              "weight": "...",
              "origin": "...",
              "amount": "..."
            }}
          ]
        }}

        TEXT TO ANALYZE:
        {text_content}
        """
        
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        st.error(f"❌ Gemini Error: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Gemini Customs Extractor")
st.info("تم تحديث المحرك لاستخدام Google Gemini لاستخراج الرموز الجمركية، بلد المنشأ، والقيمة.")
st.markdown("---")

uploaded_file = st.file_uploader("ارفع البيان الجمركي (PDF)", type=['pdf'])

if uploaded_file:
    if st.button("🚀 بدء التحليل الذكي بواسطة Gemini"):
        with st.spinner("جاري تحليل المستند واستخراج البيانات..."):
            
            # قراءة الملف
            file_bytes = uploaded_file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()

            # معالجة النص عبر Gemini
            result = process_with_gemini(full_text)
            
            if result and 'items' in result:
                items = result['items']
                
                if items:
                    st.success(f"✅ تم استخراج {len(items)} بند بنجاح.")
                    
                    # تحويل لجدول
                    df = pd.DataFrame(items)
                    
                    # ترتيب الأعمدة المطلوبة
                    cols_order = ['hs_code', 'origin', 'amount', 'description', 'qty', 'weight']
                    actual_cols = [c for c in cols_order if c in df.columns]
                    
                    # عرض الجدول التفاعلي
                    st.data_editor(df[actual_cols], use_container_width=True, num_rows="dynamic")
                    
                    # خيار تحميل البيانات
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 تحميل النتائج (CSV)", csv, "gemini_extracted_items.csv", "text/csv")
                else:
                    st.warning("⚠️ لم يتم العثور على بنود. تأكد من جودة ملف الـ PDF.")
            else:
                st.error("⚠️ فشل في تحليل البيانات. تأكد من صحة الـ API Key.")

# إرشادات للمستخدم
with st.sidebar:
    st.header("إعدادات المحرك")
    st.write("**الموديل:** Gemini 1.5 Flash (Auto-optimized)")
    st.info("""
    - تم تحسين الاستخراج للتركيز على:
        1. الرمز الجمركي (HS Code).
        2. بلد المنشأ (Origin).
        3. القيمة المالية (Amount).
    """)
