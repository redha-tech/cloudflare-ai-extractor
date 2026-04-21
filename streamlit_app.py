import streamlit as st
import pandas as pd
import json
import base64
import io
import sys

# --- 1. محاولة استيراد المكتبة بأكثر من مسار ---
try:
    from mistralai import Mistral
except (ImportError, ModuleNotFoundError):
    try:
        from mistralai.client import MistralClient as Mistral
    except:
        st.error("🚨 مكتبة Mistral غير مثبتة. يرجى التأكد من كتابة mistralai في requirements.txt وعمل Reboot App من Settings.")
        st.stop()

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus Multi-Format", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 MISTRAL_API_KEY مفقود من Secrets!")
        return None

    client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الملف إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    # البرومبت المتخصص
    prompt = (
        "Extract all items from this document (PDF or Image). "
        "Fields: hs_code, description, qty, unit_price, amount, origin. "
        "Maintain Arabic text. Return ONLY JSON with an 'items' key."
    )

    try:
        # استخدام موديل pixtral-12b-2409 للرؤية والمستندات
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
st.title("🌪️ Mistral Multi-Format Extractor")
st.markdown("يدعم ملفات الصور و الـ PDF بنظام Pixtral v1.2")

uploaded_file = st.file_uploader("ارفع الفاتورة أو المستند (PDF, JPG, PNG)", type=['pdf', 'jpg', 'jpeg', 'png'])

if uploaded_file:
    # عرض نوع الملف
    if uploaded_file.type == "application/pdf":
        st.info(f"📄 تم رفع ملف PDF: {uploaded_file.name}")
    else:
        st.image(uploaded_file, width=300)

    if st.button("🚀 ابدأ تحليل البيانات", use_container_width=True, type="primary"):
        with st.spinner("جاري الاستخراج..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                
                # تصدير إكسل
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل نتائج Excel",
                    data=buf.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.error("❌ فشل الاستخراج. تأكد من وضوح الملف.")

st.divider()
st.caption("نظام Clik-Plus المطور | Python 3.14 Environment")
