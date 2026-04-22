import streamlit as st
import pandas as pd
import json
import base64
import io
from PIL import Image
from pdf2image import convert_from_bytes

# --- 1. آلية الاستيراد المرنة ---
try:
    from mistralai import Mistral
except ImportError:
    try:
        from mistralai.client import Mistral
    except ImportError:
        st.error("❌ السيرفر لا يزال لا يرى مكتبة Mistral.")
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

# --- 3. دالة معالجة البيانات (بدون تغيير في المنطق الأساسي) ---
def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        # نستخدم دائماً jpeg كمime_type للصور المحولة لضمان التوافق
        actual_mime = mime_type if "pdf" not in mime_type and "excel" not in mime_type else "image/jpeg"
        data_url = f"data:{actual_mime};base64,{base64_file}"

        prompt = (
            "Extract all items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Important: Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON object with a single key 'items' containing the list."
        )

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": data_url}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ فشل الاتصال بمحرك Mistral: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("تحليل الفواتير (PDF, Excel, Images) باستخدام محرك **Pixtral AI**.")

# تحديث أنواع الملفات المسموح بها
uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري معالجة المستند..."):
            final_items = []
            
            # حالة 1: ملف PDF (تحويل كل صفحة لصورة ومعالجتها)
            if file_ext == 'pdf':
                images = convert_from_bytes(uploaded_file.read())
                for i, img in enumerate(images):
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    data = process_with_pixtral(buf.getvalue(), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
            
            # حالة 2: ملف Excel (قراءته كبيانات مباشرة أو تحويله لصورة - هنا سنعتمد المعالجة المباشرة لضمان الدقة)
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                # هنا يمكننا عرض البيانات مباشرة أو تحويلها لـ JSON لتناسب هيكلية التطبيق
                final_items = df_excel.to_dict(orient='records')
            
            # حالة 3: صور عادية
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
                st.warning("⚠️ لم يتم العثور على بيانات.")

st.markdown("---")
st.caption("Clik-Plus Platform v2.0 - Powered by Mistral Pixtral")
