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
        st.error("❌ السيرفر لا يزال لا يرى مكتبة Mistral. يرجى الضغط على Manage App ثم Reboot App.")
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

# --- 3. دالات المعالجة ---
def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{base64_file}"

        prompt = (
            "Extract all items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Important: Extract all values EXACTLY as they are written in the document. "
            "Do not translate, do not change language, and do not reformat text. "
            "Return ONLY a valid JSON object with a single key 'items' containing the list."
        )

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url}
                ]
            }],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ فشل الاتصال بمحرك Pixtral: {str(e)}")
        return None

def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = (
            "Extract items from the following text into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Important: Extract all values EXACTLY as they are written. Do not translate. "
            "Return ONLY a valid JSON object with a single key 'items'.\n\n"
            f"Text content:\n{text_content}"
        )
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في تحليل نص PDF: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
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
                df_raw = pd.read_excel(uploaded_file)
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                
                smart_map = {
                    'hs_code': ['hs', 'code', 'رمز', 'تنسيق'],
                    'description': ['desc', 'item', 'product', 'البيان', 'الصنف', 'الوصف'],
                    'qty': ['qnt', 'quantity', 'الكمية', 'عدد'],
                    'unit_price': ['rate', 'price', 'سعر', 'فئة'],
                    'amount': ['total', 'value', 'المبلغ', 'القيمة'],
                    'origin': ['country', 'made', 'المنشأ', 'بلد']
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

            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # --- عرض النتائج المشتركة ---
            if final_items:
                df = pd.DataFrame(final_items)
                
                # 1. Clean numbers
                for col in ['qty', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # 2. Add 2 empty rows
                empty_data = {col: [""] * 2 for col in df.columns}
                df_empty = pd.DataFrame(empty_data)

                # 3. Add Total Row
                totals = {col: "" for col in df.columns}
                totals['description'] = "TOTAL / الإجمالي"
                totals['qty'] = df['qty'].sum()
                totals['amount'] = df['amount'].sum()
                df_total = pd.DataFrame([totals])

                # 4. Merge
                df_final = pd.concat([df.astype(object), df_empty, df_total], ignore_index=True)
                
                # 5. Index starting from 1
                new_idx = list(range(1, len(df) + 1)) + [" ", "  ", "TOTAL"]
                df_final.index = new_idx

                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                
                def highlight(s):
                    return ['background-color: #ffffcc; font-weight: bold' if s.name == "TOTAL" else '' for _ in s]

                st.dataframe(df_final.style.apply(highlight, axis=1), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='ExtractedData')
                    worksheet = writer.sheets['ExtractedData']
                    total_fmt = writer.book.add_format({'bg_color': '#ffffcc', 'bold': True})
                    worksheet.set_row(len(df_final), None, total_fmt)
                
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Extracted_{uploaded_file.name}.xlsx")
            else:
                st.warning("⚠️ لم يتم العثور على بيانات منظمة.")
