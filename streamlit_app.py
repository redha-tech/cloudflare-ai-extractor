import streamlit as st
import pandas as pd
import json
import base64
import io
import importlib

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus Final", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. دالة المعالجة بنظام الاستيراد الديناميكي ---
def process_with_mistral(file_bytes, mime_type):
    # محاولة الاستيراد داخل الدالة لتجنب انهيار التطبيق عند التشغيل
    try:
        mistral_lib = importlib.import_module("mistralai")
        # محاولة الوصول للكلاس Mistral بأكثر من طريقة
        if hasattr(mistral_lib, "Mistral"):
            client = mistral_lib.Mistral(api_key=MISTRAL_KEY)
        else:
            from mistralai.client import MistralClient
            client = MistralClient(api_key=MISTRAL_KEY)
    except Exception as e:
        st.error(f"مشكلة في مكتبة Mistral: {str(e)}")
        return None

    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = "Extract all items into JSON format: hs_code, description, qty, unit_price, amount, origin. Return ONLY JSON."

    try:
        # تنفيذ الطلب
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": data_url}]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"خطأ أثناء التحليل: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🌪️ Clik-Plus | Final Workaround")
st.info("هذا الإصدار يستخدم نظام الاستيراد الديناميكي لتخطي أخطاء البيئة.")

uploaded_file = st.file_uploader("ارفع الملف (PDF أو صورة)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    if st.button("🚀 بدء الاستخراج الآن", use_container_width=True, type="primary"):
        with st.spinner("جاري المعالجة..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success("✅ تم بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # إكسل
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine='xlsxwriter')
                st.download_button("📥 تحميل إكسل", buf.getvalue(), "result.xlsx", use_container_width=True)
