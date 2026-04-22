import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF
from PIL import Image

# --- 1. الاستيراد ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. الدوال البرمجية ---

# معالجة الصور (PNG, JPG, Scanned PDF)
def process_image(file_bytes, mime_type):
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{base64_file}"
        
        prompt = "Extract items to JSON: hs_code, description, qty, unit_price, amount, origin. Arabic text safe."
        
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
        st.error(f"Vision Error: {e}")
        return None

# معالجة النص المباشر (Readable PDF)
def process_text(text_content):
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = f"Convert this text to JSON items (hs_code, description, qty, unit_price, amount, origin):\n{text_content}"
        
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Text Error: {e}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج المتكامل")

uploaded_file = st.file_uploader("ارفع ملف (PDF, Excel, PNG, JPG)", type=['pdf', 'xlsx', 'xls', 'png', 'jpg', 'jpeg'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 استخراج البيانات الآن"):
        with st.spinner("جاري معالجة الملف..."):
            final_items = []

            # حالة 1: EXCEL
            if file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # حالة 2: PDF
            elif file_ext == 'pdf':
                pdf_data = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                
                # محاولة قراءة النص أولاً (أسرع وأدق للـ Readable PDF)
                full_text = "".join([page.get_text() for page in doc])
                
                if len(full_text.strip()) > 100: # إذا وجد نص كافٍ
                    data = process_text(full_text)
                    if data and 'items' in data: final_items = data['items']
                else:
                    # إذا كان PDF عبارة عن صور (Scanned)
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        data = process_image(pix.tobytes("jpeg"), "image/jpeg")
                        if data and 'items' in data: final_items.extend(data['items'])
                doc.close()

            # حالة 3: PNG / JPG
            else:
                data = process_image(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # --- عرض النتائج ---
            if final_items:
                df = pd.DataFrame(final_items)
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Result_{uploaded_file.name}.xlsx")
