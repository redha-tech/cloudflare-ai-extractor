import streamlit as st
import pandas as pd
import json
import base64
import requests
import fitz  # PyMuPDF
import io

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Qwen Vision Pro", layout="wide", page_icon="🚢")

# استدعاء المفتاح من Secrets
# تأكد من إضافة OPENROUTER_API_KEY في ملف التكوين الخاص بك
API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- 2. محرك المعالجة الرئيسي (OpenRouter Vision) ---
def process_with_qwen_vision(file_bytes, mime_type):
    if not API_KEY:
        st.error("⚠️ مفتاح API مفقود! يرجى إضافته في Secrets.")
        return None
    
    try:
        # تحويل الملف إلى Base64
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        API_URL = "https://openrouter.ai/api/v1/chat/completions"
        
        # استخدام موديل 7B (أخف وأرخص لتجنب خطأ Credits)
        MODEL_ID = "qwen/qwen-2-vl-7b-instruct" 

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://clik-plus.streamlit.app",
            "X-Title": "Clik-Plus Customs Engine"
        }

        # هيكلة الطلب (Payload)
        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": (
                                "Extract all items from this document into a valid JSON object. "
                                "Required keys: hs_code, description, qty, weight, origin. "
                                "Keep Arabic text for description. "
                                "Return ONLY the JSON object starting with an 'items' key."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1500, # تحديد التوكنز لحل مشكلة الرصيد
            "temperature": 0.1
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
        
        if response.status_code != 200:
            error_data = response.json()
            st.error(f"❌ خطأ من المنصة: {error_data.get('error', {}).get('message', 'خطأ غير معروف')}")
            return None

        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)

    except Exception as e:
        st.error(f"❌ فشل المحرك: {str(e)}")
        return None

# --- 3. واجهة المستخدم (Streamlit UI) ---
st.title("🚢 Clik-Plus | Qwen Vision Engine")
st.markdown("""
تطبيق متخصص لاستخراج بيانات الجمارك (HS Codes، الأوزان، المنشأ) من الفواتير والملفات باستخدام الذكاء الاصطناعي الرؤيوي.
""")

uploaded_file = st.file_uploader("ارفع المستند (PDF أو صورة)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    if st.button("🚀 بدء تحليل المستند"):
        with st.spinner("جاري 'رؤية' المستند واستخراج البيانات..."):
            final_items = []
            file_bytes = uploaded_file.read()

            # معالجة ملفات PDF
            if uploaded_file.type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    # تحويل الصفحة لصورة بدقة متوسطة (150 DPI) للتوفير
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    data = process_with_qwen_vision(pix.tobytes("jpeg"), "image/jpeg")
                    if data and 'items' in data:
                        final_items.extend(data['items'])
                doc.close()
            # معالجة الصور المباشرة
            else:
                data = process_with_qwen_vision(file_bytes, uploaded_file.type)
                if data and 'items' in data:
                    final_items = data['items']

            # عرض النتائج
            if final_items:
                st.success(f"✅ تم استخراج {len(final_items)} صنف بنجاح!")
                df = pd.DataFrame(final_items)
                
                # عرض محرر البيانات التفاعلي
                st.data_editor(df, use_container_width=True, num_rows="dynamic")
                
                # خيار تحميل ملف Excel/CSV
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل البيانات المستخرجة (CSV)",
                    data=csv,
                    file_name="extracted_customs_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ لم يتم العثور على بيانات أصناف في هذا المستند.")

# --- 4. تذييل الصفحة ---
st.divider()
st.caption("نظام Clik-Plus الجمركي - يعمل بواسطة Qwen 2 VL عبر OpenRouter.")
