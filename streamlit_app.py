import streamlit as st
import pandas as pd
from mistralai import Mistral
import json
import re
import io
import base64

# --- 1. الإعدادات وجلب المفتاح ---
st.set_page_config(page_title="Mistral Vision Extractor", layout="wide")

# تأكد من إضافة MISTRAL_API_KEY في Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

def process_with_mistral_vision(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 Mistral API Key is missing!")
        return None

    client = Mistral(api_key=MISTRAL_KEY)
    
    # تحويل الملف إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = """
    Extract items from this document into a valid JSON format. 
    Required fields: hs_code, description, qty, unit_price, amount, origin.
    Return ONLY JSON with the key 'items'.
    If the document is in Arabic, extract the text as it is.
    """

    try:
        # استخدام موديل pixtral-12b-2409 أو أحدث نسخة تدعم الرؤية
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
        
        res_content = response.choices[0].message.content
        return json.loads(res_content)
    except Exception as e:
        st.error(f"Mistral Error: {str(e)}")
        return None

# --- 2. واجهة المستخدم ---
st.title("🌪️ Mistral Pixtral | Vision Mode")
st.info("هذا الوضع مخصص لاختبار قدرات الرؤية في Mistral بشكل مستقل.")

uploaded_file = st.file_uploader("ارفع صورة الفاتورة (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    if st.button("🚀 تحليل عبر Mistral Vision", use_container_width=True, type="primary"):
        with st.spinner("Mistral يقرأ الصورة الآن..."):
            file_bytes = uploaded_file.getvalue()
            mime_type = uploaded_file.type
            
            data = process_with_mistral_vision(file_bytes, mime_type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success("تم الاستخراج بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # تصدير إكسل
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine='xlsxwriter')
                st.download_button("📥 تحميل النتائج", buf.getvalue(), "mistral_results.xlsx")
            else:
                st.error("فشل في استخراج البيانات. تأكد من وضوح الصورة وصلاحية المفتاح.")

st.divider()
st.caption("Powered by Mistral AI | Pixtral Vision Model")
