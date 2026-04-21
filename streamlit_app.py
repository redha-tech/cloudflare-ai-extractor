import streamlit as st
import pandas as pd
import json
import base64
import io
import os

# --- 1. استيراد المكتبة بطريقة متوافقة مع الإصدارات الجديدة ---
try:
    # الطريقة الحديثة جداً للإصدارات +2.0
    from mistralai import Mistral
except ImportError:
    try:
        # الطريقة البديلة
        from mistralai.client import MistralClient as Mistral
    except:
        st.error("فشل نظام الاستيراد. يرجى التأكد من ملف requirements.txt")

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Mistral Vision Pro", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 المفتاح MISTRAL_API_KEY غير موجود في Secrets!")
        return None

    # تهيئة العميل (Client)
    try:
        client = Mistral(api_key=MISTRAL_KEY)
    except:
        # محاولة للنسخ الأقدم إذا لزم الأمر
        from mistralai.client import MistralClient
        client = MistralClient(api_key=MISTRAL_KEY)

    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = "Extract all items from this invoice into JSON format with keys: hs_code, description, qty, unit_price, amount, origin. Return ONLY JSON."

    try:
        # ملاحظة: في الإصدار 2.4.0 قد تختلف أسماء الدوال قليلاً
        # سنستخدم الطريقة العامة الأكثر استقراراً
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
        st.error(f"Mistral API Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🌪️ Mistral Vision | Pro Extractor")

uploaded_file = st.file_uploader("ارفع صورة المستند (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    st.image(uploaded_file, width=400)
    
    if st.button("🚀 تحليل البيانات الآن", use_container_width=True, type="primary"):
        with st.spinner("جاري المعالجة..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success("تم الاستخراج!")
                st.dataframe(df, use_container_width=True)
                
                # تحميل إكسل
                buf = io.BytesIO()
                df.to_excel(buf, index=False)
                st.download_button("📥 تحميل النتائج", buf.getvalue(), "results.xlsx", use_container_width=True)
