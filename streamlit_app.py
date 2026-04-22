import streamlit as st
import pandas as pd
import json
import io
import fitz  # PyMuPDF للقراءة النصية

# --- 1. الاستيراد ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide")
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة معالجة النص (بدون صور) ---
def process_text_with_mistral(extracted_text):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        
        # هنا نستخدم موديل أصغر وأسرع وأرخص (مثل mistral-small) لأننا نرسل نصاً فقط
        prompt = f"""
        Extract items from this text into a clean JSON format. 
        Required keys: hs_code, description, qty, unit_price, amount, origin.
        Keep Arabic text as is.
        Return ONLY JSON.
        
        Text:
        {extracted_text}
        """

        response = client.chat.complete(
            model="mistral-small-latest", # موديل نصي سريع جداً
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في معالجة النص: {str(e)}")
        return None

# --- 4. الواجهة ---
st.title("🚢 Clik-Plus | المستخرج النصي السريع")

uploaded_file = st.file_uploader("ارفع ملف PDF أو Excel", type=['pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 استخراج البيانات الآن"):
        with st.spinner("جاري القراءة الرقمية للملف..."):
            final_items = []

            # حالة PDF (قراءة نصية مباشرة)
            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                full_text = ""
                for page in doc:
                    full_text += page.get_text() # استخراج النص المباشر
                doc.close()
                
                if full_text.strip():
                    data = process_text_with_mistral(full_text)
                    if data and 'items' in data:
                        final_items = data['items']
                else:
                    st.error("⚠️ الملف لا يحتوي على نص قابل للقراءة الرقمية، ربما هو صورة!")

            # حالة Excel (قراءة مباشرة كما هي)
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # عرض النتائج
            if final_items:
                df = pd.DataFrame(final_items)
                st.success("✅ تم الاستخراج بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل Excel", output.getvalue(), "data.xlsx")
