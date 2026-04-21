import streamlit as st
import pandas as pd
import json
import base64
import io

# محاولة استيراد مرنة للتعامل مع أي نسخة مثبتة
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import MistralClient as Mistral

# إعداد الصفحة
st.set_page_config(page_title="Clik-Plus Mistral Vision", layout="wide")

# جلب المفتاح من الـ Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 MISTRAL_API_KEY is missing!")
        return None

    # تهيئة العميل
    try:
        client = Mistral(api_key=MISTRAL_KEY)
    except:
        client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الصورة إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "Extract all table items from this document into a JSON format. "
        "Keys: hs_code, description, qty, unit_price, amount, origin. "
        "Return ONLY the JSON object with the key 'items'. Preserve Arabic text."
    )

    try:
        # استخدام دالة التحدث مع الموديل (متوافقة مع Pixtral)
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
        st.error(f"API Error: {str(e)}")
        return None

# واجهة المستخدم
st.title("🚢 Clik-Plus | Mistral Vision Edition")
st.markdown("تم إصلاح نظام التثبيت ومعالجة اللغة العربية.")

uploaded_file = st.file_uploader("ارفع صورة الفاتورة (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    st.image(uploaded_file, width=400, caption="المستند المرفوع")
    
    if st.button("🚀 تحليل البيانات الآن", use_container_width=True, type="primary"):
        with st.spinner("جاري التحليل..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success("✅ تم الاستخراج بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # تصدير إكسل
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine='xlsxwriter')
                st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "results.xlsx", use_container_width=True)
            else:
                st.error("❌ فشل الاستخراج. تأكد من وضوح الصورة وصلاحية المفتاح.")
