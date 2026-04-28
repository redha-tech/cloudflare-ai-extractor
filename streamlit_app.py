import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF
from groq import Groq

# --- 1. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Auto-Model OCR", layout="wide", page_icon="🚢")

# تخصيص واجهة المستخدم
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# الحصول على المفتاح من Secrets
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

def get_latest_vision_model(client):
    try:
        # جلب قائمة الموديلات المتاحة فعلياً في حسابك الآن
        models = client.models.list()
        
        # البحث عن الموديلات التي تدعم الرؤية (Vision) والبحث عن الكلمات المفتاحية
        # سنبحث عن llama-3.3 أو llama-3.2 (النسخ المستقرة) أو qwen-vl
        available_ids = [m.id for m in models.data]
        
        # قائمة الأولويات (من الأحدث للأقدم)
        priority_list = [
            "llama-3.3-70b-versatile", # غالباً هذا هو البديل الأحدث
            "llama-3.2-90b-vision-instant", # نسخة مستقرة بديلة للـ preview
            "llama-3.2-11b-vision-instant",
            "qwen-2.5-vl-72b",
            "qwen-2-vl-7b-instruct"
        ]
        
        for model in priority_list:
            if model in available_ids:
                return model
        
        # إذا لم يجد في القائمة، يبحث عن أي شيء يحتوي على vision
        vision_models = [m.id for m in models.data if "vision" in m.id.lower()]
        if vision_models:
            return vision_models[0]
            
        return "llama-3.2-11b-vision-instant" # الموديل الاحتياطي الأخير
    except Exception as e:
        st.warning(f"⚠️ فشل التحديث التلقائي، سيتم استخدام الموديل الاحتياطي: {e}")
        return "llama-3.2-11b-vision-instant"

# --- 3. دالة المعالجة الأساسية ---
def process_with_auto_vision(file_bytes, mime_type):
    if not GROQ_API_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # اكتشاف الموديل المحدث تلقائياً
        active_model = get_latest_vision_model(client)
        
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        
        prompt = (
            "Extract items from this customs document into a structured JSON format. "
            "Required fields: hs_code, description, qty, weight, origin, invoice_number. "
            "Keep Arabic text for description and origin. "
            "Return ONLY JSON with key 'items'."
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_file}"},
                        },
                    ],
                }
            ],
            model=active_model,
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content), active_model
    except Exception as e:
        st.error(f"❌ خطأ: {str(e)}")
        return None, None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي (Auto-Update Mode)")

uploaded_file = st.file_uploader("ارفع ملف الفاتورة أو بوليصة الشحن", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل المستند الآن"):
        with st.spinner("جاري البحث عن أحدث موديل متاح ومعالجة البيانات..."):
            final_items = []
            used_model = ""

            if file_ext == 'pdf':
                pdf_content = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data, used_model = process_with_auto_vision(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data, used_model = process_with_auto_vision(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success(f"✅ تم الاستخراج بنجاح باستخدام موديل: `{used_model}`")
                
                df = pd.DataFrame(final_items)
                # عرض محرر البيانات للسماح بالتعديل اليدوي
                edited_df = st.data_editor(df, use_container_width=True)
                
                # تصدير لملف Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    edited_df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل النتائج (Excel)",
                    data=output.getvalue(),
                    file_name="Customs_Data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
