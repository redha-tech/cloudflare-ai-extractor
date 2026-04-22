import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. آلية الاستيراد ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. الدوال البرمجية ---

def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
        data_url = f"data:{actual_mime};base64,{base64_file}"

        prompt = (
            "Extract items into JSON with these keys: "
            "hs_code, description, qty, unit_price, amount, origin, weight. "
            "Return ONLY a JSON object with a single key 'items'."
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
        st.error(f"Error: {str(e)}")
        return None

def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = (
            "Extract items from the text into JSON: hs_code, description, qty, unit_price, amount, origin, weight. "
            f"Keep Arabic. Return ONLY JSON with key 'items'.\n\nText:\n{text_content}"
        )
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Text Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري معالجة المستند..."):
            final_items = []

            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                full_text = "".join([page.get_text() for page in doc])
                doc.close()
                if full_text.strip():
                    data = process_pdf_text(full_text)
                    if data and 'items' in data: final_items = data['items']
                else:
                    doc = fitz.open(stream=pdf_content, filetype="pdf")
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        data = process_with_pixtral(pix.tobytes("jpeg"), "image/jpeg")
                        if data and 'items' in data: final_items.extend(data['items'])
                    doc.close()
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')
            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                df.index = df.index + 1
                df.index.name = "#"

                # تحويل الأعمدة الرقمية لضمان دقة الحساب
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce').fillna(0)

                # --- 1. تنبيهات القيم الصفرية في سطر واحد ---
                zero_items = df[df['amount'] <= 0].index.tolist()
                if zero_items:
                    items_str = ", ".join([f"#{i}" for i in zero_items])
                    st.warning(f"⚠️ تنبيه: تم العثور على قيم صفرية أو خصومات في الأصناف التالية: {items_str}")

                # --- 2. إضافة صف الإجمالي (Total) في النهاية ---
                total_amount = df['amount'].sum()
                
                # عرض النتائج
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # عرض الإجمالي بشكل واضح
                st.info(f"💰 **إجمالي المبلغ الكلي (Total Amount): {total_amount:,.2f}**")
                
                # تحميل Excel مع صف الإجمالي
                df_with_total = df.copy()
                # إضافة صف الإجمالي في نهاية الـ DataFrame للأكسل
                df_with_total.loc['Total'] = None
                df_with_total.at['Total', 'amount'] = total_amount
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_with_total.to_excel(writer, index=True)
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx"
                )
            else:
                st.warning("⚠️ لم يتم العثور على بيانات.")
