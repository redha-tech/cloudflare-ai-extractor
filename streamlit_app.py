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
    try:
        from mistralai.client import Mistral
    except ImportError:
        st.error("❌ المكتبة غير مثبتة. يرجى إعادة تشغيل التطبيق.")
        st.stop()

# --- 2. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالات المعالجة الذكية ---

def get_smart_prompt(context_type="image", text_content=None):
    base_prompt = (
        "You are an AI Data Scientist specialized in Global Trade Documents. "
        "Your goal is to find the 'Logic' of the invoice, regardless of its layout:\n"
        "1. **Semantic Mapping**: Identify columns by content:\n"
        "   - **HS_CODE**: Look for 6, 8, or 10 digits. Ignore 13-digit barcodes.\n"
        "   - **DESCRIPTION**: The main text field in the row.\n"
        "   - **QTY**: Integers near description.\n"
        "   - **PRICE**: Decimal numbers.\n"
        "   - **ORIGIN**: Country names or 'C/O'.\n"
        "2. **Table Reconstruction**: Capture every single item row. Do not skip.\n"
        "3. **Zero Translation**: Extract text EXACTLY as written.\n"
        "4. **Strict JSON**: Return ONLY a valid JSON object with key 'items'."
    )
    if context_type == "text":
        return f"{base_prompt}\n\nInvoice Content:\n{text_content}"
    return base_prompt

def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{base64_file}"
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [{"type": "text", "text": get_smart_prompt()}, {"type": "image_url", "image_url": data_url}]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في محرك الصور: {str(e)}")
        return None

def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": get_smart_prompt("text", text_content)}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في تحليل النص: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرئيسية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, Images)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري تحليل المستند بذكاء..."):
            final_items = []

            # معالجة PDF
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

            # معالجة Excel
            elif file_ext in ['xlsx', 'xls']:
                df_raw = pd.read_excel(uploaded_file)
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                smart_map = {
                    'hs_code': ['hs', 'code', 'commodity', 'tariff', 'بند', 'رمز'],
                    'description': ['desc', 'item', 'product', 'البيان', 'الوصف'],
                    'qty': ['qty', 'quantity', 'الكمية', 'عدد'],
                    'unit_price': ['price', 'rate', 'سعر', 'فئة'],
                    'amount': ['amount', 'total', 'المبلغ', 'القيمة'],
                    'origin': ['origin', 'c/o', 'made', 'المنشأ', 'بلد']
                }
                new_cols = {}
                for official, synonyms in smart_map.items():
                    for actual in df_raw.columns:
                        if any(syn.lower() in actual.lower() for syn in synonyms):
                            new_cols[actual] = official
                            break
                df_raw = df_raw.rename(columns=new_cols)
                required = ['hs_code', 'description', 'qty', 'unit_price', 'amount', 'origin']
                for col in required:
                    if col not in df_raw.columns: df_raw[col] = ""
                final_items = df_raw[required].to_dict(orient='records')

            # معالجة الصور
            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # --- 5. عرض ومعالجة النتائج النهائية ---
            if final_items:
                df = pd.DataFrame(final_items)
                for col in ['qty', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # إضافة صفوف فارغة وسطرة الإجمالي
                df_empty = pd.DataFrame({col: [""] * 2 for col in df.columns})
                totals = {col: "" for col in df.columns}
                totals['description'] = "TOTAL / الإجمالي"
                totals['qty'] = df['qty'].sum()
                totals['amount'] = df['amount'].sum()
                df_total = pd.DataFrame([totals])

                df_final = pd.concat([df.astype(object), df_empty, df_total], ignore_index=True)
                df_final.index = list(range(1, len(df) + 1)) + [" ", "  ", "TOTAL"]

                st.success(f"✅ تم تحليل {len(df)} صنف بنجاح!")
                
                def highlight(s):
                    return ['background-color: #ffffcc; font-weight: bold' if s.name == "TOTAL" else '' for _ in s]
                
                st.dataframe(df_final.style.apply(highlight, axis=1), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='ExtractedData')
                    total_fmt = writer.book.add_format({'bg_color': '#ffffcc', 'bold': True, 'border': 1})
                    writer.sheets['ExtractedData'].set_row(len(df_final), None, total_fmt)
                
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Extracted_{uploaded_file.name}.xlsx")
            else:
                st.warning("⚠️ لم يتم العثور على بيانات منظمة.")
