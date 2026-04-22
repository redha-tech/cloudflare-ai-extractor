import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. آلية الاستيراد المرنة ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. التعليمات الذكية للنموذج ---
MASTER_PROMPT = (
    "Analyze the invoice and extract items into JSON. Map different column names to these exact keys: "
    "hs_code, description (keep Arabic), qty, unit_price, amount, origin (keep Arabic), "
    "gross_weight, net_weight, pkg, invoice_number. "
    "If a value is missing, use null. Return ONLY a JSON object with key 'items'."
)

# --- 4. الدوال البرمجية ---

def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
        data_url = f"data:{actual_mime};base64,{base64_file}"

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": MASTER_PROMPT},
                {"type": "image_url", "image_url": data_url}
            ]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Vision Error: {str(e)}")
        return None

def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = f"{MASTER_PROMPT}\n\nText content:\n{text_content}"
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Text Error: {str(e)}")
        return None

# --- 5. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, Images)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري تحليل البيانات وفحص القيم..."):
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
                df_excel = pd.read_excel(uploaded_file).ffill()
                final_items = df_excel.to_dict(orient='records')

            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                
                # تنظيف البيانات الرقمية
                num_cols = ['qty', 'unit_price', 'amount', 'gross_weight', 'net_weight']
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # تنبيه الخصومات والقيم الصفرية في سطر واحد
                zero_indices = df[(df['unit_price'] <= 0) | (df['amount'] <= 0)].index.tolist()
                if zero_indices:
                    short_list = ", ".join([f"#{i+1}" for i in zero_indices])
                    st.warning(f"⚠️ تنبيه: تم العثور على قيم صفرية أو خصومات في الأسطر: {short_list}")

                # --- إضافة سطر TOTAL الديناميكي ---
                totals = {
                    'description': '--- TOTAL ---',
                    'qty': df['qty'].sum(),
                    'amount': df['amount'].sum(),
                    'gross_weight': df['gross_weight'].sum() if 'gross_weight' in df.columns else 0,
                    'net_weight': df['net_weight'].sum() if 'net_weight' in df.columns else 0
                }
                
                # دمج سطر المجموع
                df_with_total = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
                
                # إعداد الترقيم: 1، 2، 3... ثم TOTAL
                new_index = list(range(1, len(df) + 1)) + ["TOTAL"]
                df_with_total.index = new_index
                df_with_total.index.name = "#"

                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df_with_total, use_container_width=True)
                
                # تحميل Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_with_total.to_excel(writer, index=True, sheet_name='ExtractedData')
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx"
                )
            else:
                st.warning("⚠️ لم يتم العثور على بيانات منظمة.")
