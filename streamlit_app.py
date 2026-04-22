import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF للتعامل مع الـ PDF

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

# --- 3. دالة معالجة البيانات ---
def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        # نستخدم image/jpeg كنوع افتراضي للبيانات الصورية المرسلة
        actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
        data_url = f"data:{actual_mime};base64,{base64_file}"

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
        st.error(f"❌ فشل الاتصال بمحرك Mistral: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("تحليل الفواتير والمستندات باستخدام محرك **Pixtral AI**.")

# تحديث الأنواع المسموح بها لتشمل PDF و Excel
uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري معالجة المستند..."):
            final_items = []

            # الحالة 1: ملفات PDF (تحويل كل صفحة لصورة ومعالجتها)
            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("jpeg")
                    data = process_with_pixtral(img_bytes, "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()

            # الحالة 2: ملفات Excel (قراءة مباشرة لضمان الدقة الرقمية)
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # الحالة 3: الصور العادية
            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items.extend(data['items'])

            # --- عرض النتائج المشتركة ---
            if final_items:
                df = pd.DataFrame(final_items)
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='ExtractedData')
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ لم يتم العثور على بيانات منظمة.")

st.markdown("---")
st.caption("Clik-Plus Platform v3.0 - Powered by Mistral Pixtral")
