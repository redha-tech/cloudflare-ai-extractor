import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF
import google.generativeai as genai
import re

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart Extraction", layout="wide")

# --- 2. جلب المفاتيح بأمان من Secrets (بدون كتابة أي مفتاح هنا) ---
OPENROUTER_KEY = st.secrets.get("OPENROUTER_API_KEY")
GEMINI_KEY = st.secrets.get("GEMINI_KEY")

# --- 3. دالة محرك Gemini (اتصال مباشر) ---
def process_with_gemini(file_bytes, mime_type):
    if not GEMINI_KEY:
        st.error("⚠️ مفتاح Gemini مفقود في الـ Secrets!")
        return None
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # اكتشاف الموديلات المتاحة للحساب (لتجنب خطأ 404)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # اختيار أفضل موديل متاح (يفضل Flash)
        target_model = next((m for m in available_models if "flash" in m.lower()), available_models[0])
        
        model = genai.GenerativeModel(model_name=target_model)
        
        prompt = """
        Extract all items from this document into a structured JSON object.
        Required fields for each item: hs_code, description, qty, weight, origin.
        Return ONLY the JSON object with an 'items' key.
        """
        
        # إرسال البيانات (رؤية + نص)
        content = [
            {"mime_type": "image/jpeg", "data": file_bytes},
            prompt
        ]
        
        response = model.generate_content(content)
        
        # تنظيف النص المستخرج لضمان استخراج JSON فقط
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response.text)

    except Exception as e:
        st.error(f"❌ فشل محرك Gemini: {str(e)}")
        return None

# --- 4. دالة محرك Qwen (عبر OpenRouter) ---
def process_with_qwen(file_bytes, mime_type):
    if not OPENROUTER_KEY:
        st.error("⚠️ مفتاح OpenRouter مفقود!")
        return None
    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        API_URL = "https://openrouter.ai/api/v1/chat/completions"
        MODEL_ID = "qwen/qwen-2-vl-72b-instruct" 

        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all items into JSON with 'items' key. Fields: hs_code, description, qty, weight, origin."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
        res_json = response.json()
        
        if 'choices' in res_json:
            content = res_json['choices'][0]['message']['content']
            return json.loads(content)
        else:
            st.error(f"خطأ من OpenRouter: {res_json}")
            return None

    except Exception as e:
        st.error(f"❌ فشل محرك Qwen: {str(e)}")
        return None

# --- 5. واجهة المستخدم (UI) ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("---")

# اختيار المحرك
engine_choice = st.sidebar.radio(
    "اختر محرك المعالجة:",
    ("Gemini (Direct Connection)", "Qwen (OpenRouter)"),
    help="Gemini غالباً ما يكون أسرع في الاتصال المباشر، بينما Qwen قوي جداً في تحليل الجداول المعقدة."
)

uploaded_file = st.file_uploader("ارفع فاتورة أو قائمة تعبئة (صورة أو PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 بدء استخراج البيانات"):
        with st.spinner(f"جاري التحليل باستخدام {engine_choice}..."):
            final_items = []
            file_bytes = uploaded_file.read()
            
            # تحديد دالة المعالجة المطلوبة
            process_func = process_with_gemini if "Gemini" in engine_choice else process_with_qwen

            # معالجة ملفات PDF (تحويل كل صفحة لصورة)
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_func(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            # معالجة الصور المباشرة
            else:
                data = process_func(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            # عرض النتائج
            if final_items:
                st.success(f"✅ تم استخراج {len(final_items)} صنف بنجاح!")
                df = pd.DataFrame(final_items)
                st.data_editor(df, use_container_width=True)
                
                # خيار تحميل ملف Excel
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 تحميل النتائج كـ CSV", csv, "extracted_data.csv", "text/csv")
            else:
                st.error("لم يتم العثور على بيانات. تأكد من وضوح الملف وصحة المفاتيح.")
