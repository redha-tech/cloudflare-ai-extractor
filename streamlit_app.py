import streamlit as st
import pandas as pd
import json
import base64
import io
import time
import fitz  # PyMuPDF

# --- 1. الاستيراد ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
        data_url = f"data:{actual_mime};base64,{base64_file}"

        prompt = (
            "Extract all items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Return ONLY a valid JSON object with a single key 'items'."
        )

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": data_url}
            ]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        if "429" in str(e):
            st.warning("🔄 تم الوصول للحد الأقصى للطلبات، سأنتظر قليلاً ثم أحاول مجدداً...")
            time.sleep(2) # انتظار ثانيتين
            return None
        st.error(f"❌ خطأ: {str(e)}")
        return None

# --- 4. الواجهة ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع ملف PDF أو Excel", type=['pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري المعالجة..."):
            final_items = []

            # حالة PDF
            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("jpeg")
                    
                    data = process_with_pixtral(img_bytes, "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                    
                    # أهم سطر: انتظار ثانية بين كل صفحة وصفحة لتجنب الخطأ 429
                    time.sleep(1) 
                doc.close()

            # حالة Excel
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # عرض النتائج
            if final_items:
                df = pd.DataFrame(final_items)
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button("📥 تحميل Excel", output.getvalue(), 
                                 file_name=f"Extracted_{uploaded_file.name}.xlsx")
