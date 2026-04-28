import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF
from groq import Groq # استيراد مكتبة Groq بدلاً من Mistral

# --- 2. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Qwen Smart OCR", layout="wide", page_icon="🚢")

# الحصول على مفتاح Groq من Secrets
GROQ_KEY = st.secrets.get("GROQ_API_KEY")

# --- 3. دالة معالجة البيانات باستخدام Qwen (Vision) ---
def process_with_qwen(file_bytes, mime_type):
    if not GROQ_KEY:
        st.error("⚠️ مفتاح GROQ_API_KEY مفقود!")
        return None
    try:
        client = Groq(api_key=GROQ_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        # تحضير الطلب لنموذج Qwen أو Llama-Vision المتاح على Groq
        # ملاحظة: استبدل اسم الموديل بـ qwen-2.5-vl-11b إذا كان متاحاً في حسابك
        model_name = "llama-3.2-11b-vision-preview" 
        
        prompt = (
            "Analyze this customs document image. Extract all items into a JSON object. "
            "Keys: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON with a single key 'items'."
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_file}",
                            },
                        },
                    ],
                }
            ],
            model=model_name,
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ فشل الاتصال بمحرك Groq/Qwen: {str(e)}")
        return None

# --- واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي (Qwen Engine)")
st.markdown("تحليل الفواتير الجمركية باستخدام نماذج **Vision** المتطورة عبر Groq.")

uploaded_file = st.file_uploader("ارفع المستند (PDF, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 استخراج البيانات الآن"):
        with st.spinner("جاري تحليل المستند باستخدام Qwen..."):
            final_items = []

            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                
                # في نماذج Vision، الأفضل دائماً تحويل صفحات الـ PDF لصور
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

            # --- عرض النتائج ---
            if final_items:
                df = pd.DataFrame(final_items)
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                # إضافة الوزن وبلد المنشأ للجدول المعروض
                st.dataframe(df, use_container_width=True)
                
                # خيار التحميل
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(label="📥 تحميل النتائج كملف Excel", 
                                 data=output.getvalue(), 
                                 file_name="extracted_customs_data.xlsx")
