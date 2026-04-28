import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF
from groq import Groq

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Vision", layout="wide", page_icon="🚢")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة المعالجة المخصصة لـ Qwen ---
def process_with_qwen(file_bytes, mime_type):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # تحديد موديل Qwen المتوفر على منصة Groq
        # تأكد من أن هذا الاسم هو المتاح في حسابك (مثل qwen-2.5-72b-vl أو qwen-2-vl-7b-instruct)
        MODEL_ID = "qwen-2.5-vl-72b" 

        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        prompt = (
            "Extract items from this customs invoice into JSON. "
            "Fields: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text. Return ONLY JSON with key 'items'."
        )

        # التنسيق الصحيح لنماذج Qwen-VL التي تقبل الصور
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_file}"}
                        }
                    ]
                }
            ],
            model=MODEL_ID,
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في محرك Qwen: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen Vision Engine")
st.markdown("استخراج البيانات باستخدام نموذج **Qwen** حصراً.")

uploaded_file = st.file_uploader("ارفع الملف (PDF أو صورة)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل باستخدام Qwen"):
        with st.spinner("جاري المعالجة عبر Qwen..."):
            final_items = []

            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                
                # Qwen-VL يحتاج لصور، لذا سنحول كل صفحة PDF لصورة
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                # معالجة الصور المباشرة
                data = process_with_qwen(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                st.success("✅ تم الاستخراج بنجاح!")
                st.data_editor(df, use_container_width=True)
                
                # تصدير لملف Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button("📥 تحميل النتائج", output.getvalue(), "Qwen_Data.xlsx")
