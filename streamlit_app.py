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

# --- 3. دالة معالجة البيانات (للصور فقط) ---
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
            "Important: Keep Arabic text for description and origin. "
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

# --- دالة معالجة النصوص المستخرجة من الـ PDF ---
def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = (
            "Extract items from the following text into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON object with a single key 'items'.\n\n"
            f"Text content:\n{text_content}"
        )
        response = client.chat.complete(
            model="mistral-small-latest", # موديل نصي سريع ودقيق
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في تحليل نص PDF: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("تحليل الفواتير والمستندات باستخدام محرك **Mistral AI**.")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري معالجة المستند..."):
            final_items = []

            # --- التعديل هنا: منطق الـ PDF الجديد ---
            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                
                # استخراج كافة النصوص من الصفحات
                full_text = ""
                for page in doc:
                    full_text += page.get_text()
                doc.close()
                
                if full_text.strip():
                    # معالجة النص مباشرة (للملفات القابلة للقراءة)
                    data = process_pdf_text(full_text)
                    if data and 'items' in data:
                        final_items = data['items']
                else:
                    st.warning("⚠️ لم يتم العثور على نص رقمي في الـ PDF، جاري محاولة تحليله كصور...")
                    # كخطة احتياطية إذا كان الـ PDF عبارة عن صور (Scanner)
                    doc = fitz.open(stream=pdf_content, filetype="pdf")
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        data = process_with_pixtral(pix.tobytes("jpeg"), "image/jpeg")
                        if data and 'items' in data:
                            final_items.extend(data['items'])
                    doc.close()

            # الحالة 2: ملفات Excel (بدون تغيير)
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # الحالة 3: الصور (بدون تغيير)
            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

         # --- عرض النتائج المشتركة وتعديل الترقيم وإضافة الإجمالي مع تنسيق نظيف ---
            if final_items:
                df = pd.DataFrame(final_items)

                # 1. تنظيف البيانات الرقمية للأصناف الأساسية
                num_cols = ['qty', 'amount']
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # 2. جعل الترقيم يبدأ من 1 للأصناف
                df.index = range(1, len(df) + 1)
                df.index.name = "#"

                # 3. إنشاء الأسطر الفارغة (بدون None وبدون أرقام)
                # نقوم بإنشاء DataFrame بأسطر فارغة تماماً ""
                empty_data = {col: [""] * 2 for col in df.columns}
                df_empty = pd.DataFrame(empty_data)

                # 4. إنشاء سطر الإجمالي
                totals = {col: "" for col in df.columns}
                totals['description'] = "TOTAL / الإجمالي"
                totals['qty'] = df['qty'].sum()
                totals['amount'] = df['amount'].sum()
                df_total = pd.DataFrame([totals])

                # 5. دمج الكل: الأصناف + السطرين الفارغين + الإجمالي
                df_final = pd.concat([df.astype(object), df_empty, df_total], ignore_index=True)

                # تحديث الفهرس ليظهر بشكل احترافي
                new_index = list(range(1, len(df) + 1)) + [" ", "  ", "TOTAL"]
                df_final.index = new_index

                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")

                # 6. تنسيق التلوين لسطر TOTAL فقط
                def highlight_total(s):
                    return ['background-color: #ffffcc; font-weight: bold' if s.name == "TOTAL" else '' for _ in s]

                styled_df = df_final.style.apply(highlight_total, axis=1)
                
                # عرض الجدول في streamlit
                st.dataframe(styled_df, use_container_width=True)
                
                # 7. تجهيز ملف Excel المحمل
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='ExtractedData')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['ExtractedData']
                    # تنسيق السطر الأخير في إكسل
                    total_format = workbook.add_format({'bg_color': '#ffffcc', 'bold': True, 'border': 1})
                    worksheet.set_row(len(df_final), None, total_format)
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ لم يتم العثور على بيانات منظمة.")
