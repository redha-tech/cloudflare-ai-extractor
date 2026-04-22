import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. إعدادات الواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. التعليمات الذكية للنموذج (البرومبت الموحد) ---
# هنا نطلب من النظام فهم "المعنى" بغض النظر عن المسمى في الفاتورة
MASTER_PROMPT = (
    "Analyze the provided document and extract items into a structured JSON format. "
    "Even if the column names in the document are different or in different languages, map them to these exact keys:\n"
    "1. hs_code: (Harmonized System code, digits)\n"
    "2. description: (The product name or details, keep Arabic if present)\n"
    "3. qty: (Quantity)\n"
    "4. unit_price: (Price per unit)\n"
    "5. amount: (Total line amount/subtotal)\n"
    "6. origin: (Country of origin/made in, keep Arabic if present)\n"
    "7. gross_weight: (Total weight including packaging)\n"
    "8. net_weight: (Actual product weight)\n"
    "9. pkg: (Package type like PK, Pallet, Box)\n"
    "10. invoice_number: (The invoice reference number found in the document)\n\n"
    "Return ONLY a JSON object with a single key 'items' containing the list of objects."
)

# --- 3. الدوال البرمجية ---

def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY: return None
    try:
        from mistralai import Mistral
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
        from mistralai import Mistral
        client = Mistral(api_key=MISTRAL_KEY)
        full_prompt = f"{MASTER_PROMPT}\n\nDocument Text Content:\n{text_content}"
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Text Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, Images)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري التعرف على المسميات وتحليل القيم..."):
            final_items = []

            # معالجة الملفات حسب النوع
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
                # معالجة ملفات إكسل بملء الخلايا المدمجة تلقائياً
                df_excel = pd.read_excel(uploaded_file).ffill()
                # نرسل بيانات الإكسل للنموذج ليعيد ترتيب الأعمدة حسب المطلوب
                data = process_pdf_text(df_excel.to_string())
                if data and 'items' in data: final_items = data['items']

            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                
                # تحويل القيم لنوع رقمي لضمان دقة العمليات الحسابية
                cols_to_fix = ['qty', 'amount', 'gross_weight', 'net_weight', 'unit_price']
                for c in cols_to_fix:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                # عرض تنبيه الخصومات في سطر واحد
                zero_rows = df[df['amount'] == 0].index.tolist()
                if zero_rows:
                    st.warning(f"⚠️ تنبيه: تم العثور على أسطر صفرية/خصم في السطور رقم: {', '.join(map(str, [r+1 for r in zero_rows]))}")

                # --- إضافة سطر TOTAL كآخر سطر في الجدول ---
                totals_row = {
                    'description': '--- TOTAL ---',
                    'qty': df['qty'].sum(),
                    'amount': df['amount'].sum(),
                    'gross_weight': df['gross_weight'].sum(),
                    'net_weight': df['net_weight'].sum(),
                    'hs_code': None, 'unit_price': None, 'origin': None, 'pkg': None, 'invoice_number': None
                }
                
                df_final = pd.concat([df, pd.DataFrame([totals_row])], ignore_index=True)
                
                # إعداد الفهرس (Index) ليظهر كأرقام ثم "TOTAL"
                new_idx = list(range(1, len(df) + 1)) + ["TOTAL"]
                df_final.index = new_idx

                st.success(f"✅ تم تحليل {len(df)} صنف بنجاح!")
                st.dataframe(df_final, use_container_width=True)

                # تصدير ملف Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='ExtractedData')
                
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Result_{uploaded_file.name}.xlsx")
            else:
                st.error("❌ لم نتمكن من استخراج البيانات. تأكد من وضوح الملف.")
