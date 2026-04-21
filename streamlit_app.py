import streamlit as st
import pandas as pd
import json
import base64
import io
import subprocess
import sys

# --- 1. إجبار السيرفر على تثبيت المكتبات (الحل النهائي لـ ImportError) ---
@st.cache_resource
def install_dependencies():
    try:
        from mistralai import Mistral
    except (ImportError, ModuleNotFoundError):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "mistralai"])

# تنفيذ التثبيت
install_dependencies()

# استدعاء العميل بعد التأكد من التثبيت
try:
    from mistralai import Mistral
except ImportError:
    # محاولة للأصدارات القديمة جداً كخطة بديلة
    from mistralai.client import MistralClient as Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide")

# جلب المفتاح من Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_invoice(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ خطأ: مفتاح API غير موجود في إعدادات Secrets!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
        
        # تحويل الملف لـ Base64
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{base64_file}"

        prompt = (
            "Extract these fields into JSON: hs_code, description, qty, unit_price, amount, origin. "
            "Keep Arabic text as is. Return ONLY a JSON object with an 'items' key."
        )

        # تنفيذ الطلب (متوافق مع Pixtral)
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
        st.error(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.info("هذا الإصدار يحتوي على معالج تلقائي للمكتبات لضمان التشغيل.")

uploaded_file = st.file_uploader("ارفع الفاتورة (صورة فقط حالياً للتجربة)", type=['jpg', 'png', 'jpeg'])

if uploaded_file:
    if st.button("🚀 بدء الاستخراج الآن", use_container_width=True, type="primary"):
        with st.spinner("جاري الاتصال بالسيرفر وتحليل البيانات..."):
            data = process_invoice(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                
                # تجهيز ملف إكسل للتحميل
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=buf.getvalue(),
                    file_name="extracted_invoice.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ لم نتمكن من العثور على بيانات منظمة. تأكد من جودة الصورة.")

elif not MISTRAL_KEY:
    st.warning("🔒 يرجى إضافة MISTRAL_API_KEY في قسم Secrets لتفعيل التطبيق.")
