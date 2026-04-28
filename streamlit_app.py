import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF
from groq import Groq

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen 3 Engine", layout="wide", page_icon="🚢")

# استدعاء المفتاح (تأكد أن المفتاح يدعم الموديل المذكور في صورتك)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# --- 2. دالة المعالجة المخصصة لـ Qwen 3 ---
def process_with_qwen3(file_bytes, mime_type):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح API مفقود في Secrets!")
        return None
    
    try:
        # ملاحظة: إذا كنت تستخدم OpenRouter أو منصة مشابهة للصورة، تأكد من تعديل base_url إذا لزم الأمر
        client = Groq(api_key=GROQ_API_KEY) 
        
        # الاسم الدقيق من صورتك
        MODEL_ID = "qwen/qwen3-32b" 

        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        prompt = (
            "Extract items from this document into JSON format. "
            "Required keys: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON object with an 'items' key."
        )

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
        st.error(f"❌ خطأ في محرك Qwen 3: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | Qwen 3 Vision Engine")
st.markdown(f"يتم الآن استخدام النموذج: `{ 'qwen/qwen3-32b' }` المستخرج من صورتك.")

uploaded_file = st.file_uploader("ارفع ملف الفاتورة أو المستند", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 استخراج البيانات الآن"):
        with st.spinner("جاري التحليل بواسطة Qwen 3..."):
            final_items = []

            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                for page in doc:
                    # تحويل الصفحة لصورة بجودة عالية
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_with_qwen3(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_with_qwen3(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                df = pd.DataFrame(final_items)
                st.success("✅ تم الاستخراج بنجاح!")
                # عرض البيانات في محرر تفاعلي
                st.data_editor(df, use_container_width=True)
                
                # تصدير الملف
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), "Qwen3_Customs_Data.xlsx")
