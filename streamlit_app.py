import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF
import google.generativeai as genai
import re

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart Extraction Test", layout="wide")

# جلب المفاتيح من Secrets
OPENROUTER_KEY = st.secrets.get("OPENROUTER_API_KEY")
# هنا نضع مفتاح Gemini الذي اخترته للاختبار
GEMINI_KEY = "AIzaSyCdzDnBc98eW70NaD4p2IsFJsS8oNYaMaw" 

# --- دالة محرك Qwen (عبر OpenRouter) ---
def process_with_qwen(file_bytes, mime_type):
    if not OPENROUTER_KEY:
        st.error("⚠️ مفتاح OpenRouter مفقود!")
        return None
    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        API_URL = "https://openrouter.ai/api/v1/chat/completions"
        MODEL_ID = "qwen/qwen-2-vl-72b-instruct" 

        headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
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
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"❌ فشل Qwen: {str(e)}")
        return None

# --- دالة محرك Gemini (مباشر) ---
def process_with_gemini(file_bytes, mime_type):
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # اكتشاف الموديل المتاح تلقائياً (تجنباً لخطأ 404)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = next((m for m in available_models if "flash" in m.lower()), available_models[0])
        
        model = genai.GenerativeModel(model_name=target_model)
        
        prompt = "Extract items from this document into a JSON object with 'items' key. Required fields: hs_code, description, qty, weight, origin."
        
        # تحضير الصورة/الملف لـ Gemini
        content = [{"mime_type": "image/jpeg", "data": file_bytes}, prompt]
        
        response = model.generate_content(content)
        # تنظيف النص المستخرج لضمان أنه JSON فقط
        clean_json = re.sub(r'```json|```', '', response.text).strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"❌ فشل Gemini: {str(e)}")
        return None

# --- الواجهة ---
st.title("🚢 Clik-Plus | اختبار المحركات الذكية")

# اختيار المحرك يدوياً للاختبار
engine_choice = st.radio("اختر محرك المعالجة:", ("Gemini (Direct)", "Qwen (OpenRouter)"), horizontal=True)

uploaded_file = st.file_uploader("ارفع المستند (صورة أو PDF)", type=['png', 'jpg', 'pdf'])

if uploaded_file:
    if st.button("🚀 بدء التحليل"):
        with st.spinner(f"جاري المعالجة عبر {engine_choice}..."):
            final_items = []
            file_bytes = uploaded_file.read()
            
            # تحديد الدالة بناءً على الاختيار
            process_func = process_with_gemini if engine_choice == "Gemini (Direct)" else process_with_qwen

            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    data = process_func(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            else:
                data = process_func(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            if final_items:
                st.success(f"تم الاستخراج بنجاح باستخدام {engine_choice}")
                st.data_editor(pd.DataFrame(final_items), use_container_width=True)
            else:
                st.error("لم نتمكن من استخراج بيانات. يرجى التحقق من المفاتيح أو جودة الملف.")
