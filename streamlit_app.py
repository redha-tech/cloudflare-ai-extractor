import streamlit as st
import pandas as pd
import json
import base64
import io
from PIL import Image
from pdf2image import convert_from_bytes

# --- 1. آلية الاستيراد المرنة ---
try:
    from mistralai import Mistral
except ImportError:
    st.error("❌ مكتبة Mistral مفقودة. يرجى إضافتها إلى requirements.txt")
    st.stop()

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Vision OCR", layout="wide", page_icon="🚢")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دوال المعالجة والتحويل ---

def file_to_base64_image(image_obj):
    """تحويل كائن الصورة إلى Base64"""
    buffered = io.BytesIO()
    # تحويل الصورة إلى RGB للتأكد من توافقها مع JPEG
    rgb_img = image_obj.convert('RGB')
    rgb_img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_image_with_pixtral(image_obj):
    """إرسال صورة واحدة إلى Pixtral واستخراج البيانات"""
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
        base64_str = file_to_base64_image(image_obj)
        data_url = f"data:image/jpeg;base64,{base64_str}"

        prompt = (
            "Extract all items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Important: Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON object with a single key 'items'."
        )

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url}
                ]
            }],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ خطأ في المعالجة: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج البصري الذكي")
st.info("سيتم تحويل المستندات (PDF/Excel) إلى صور لضمان دقة الاستخراج باستخدام Pixtral AI.")

uploaded_file = st.file_uploader("ارفع المستند (PDF, Excel, Images)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    all_pages_images = []

    # منطق التحويل بناءً على نوع الملف
    if file_ext == 'pdf':
        with st.spinner("جاري تحويل صفحات PDF إلى صور..."):
            all_pages_images = convert_from_bytes(uploaded_file.read())
            st.success(f"✅ تم تحويل {len(all_pages_images)} صفحة.")
    
    elif file_ext in ['xlsx', 'xls']:
        with st.spinner("جاري معالجة ملف Excel..."):
            # للاكسل: سنقرأه كبيانات ونعرضه، أو يمكنك تحويله لصورة
            # هنا سنقوم بتحويله لبيانات مباشرة لأنها أدق للاكسل برمجياً
            df_excel = pd.read_excel(uploaded_file)
            st.write("معاينة ملف Excel:")
            st.dataframe(df_excel.head())
            if st.button("🚀 استخراج البيانات من Excel"):
                # هنا يمكنك إضافة منطق خاص للاكسل أو معاملته كصورة عبر مكتبات أخرى
                st.session_state.final_df = df_excel
    
    else:
        all_pages_images = [Image.open(uploaded_file)]

    # زر المعالجة للصور و PDF
    if all_pages_images and st.button("🚀 بدء التحليل البصري"):
        final_items = []
        progress_bar = st.progress(0)
        
        for idx, img in enumerate(all_pages_images):
            with st.spinner(f"جاري معالجة الصفحة {idx+1}..."):
                result = process_image_with_pixtral(img)
                if result and 'items' in result:
                    final_items.extend(result['items'])
            progress_bar.progress((idx + 1) / len(all_pages_images))
        
        if final_items:
            df = pd.DataFrame(final_items)
            st.session_state.final_df = df
            st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
        else:
            st.error("لم يتم العثور على بيانات.")

# عرض النتائج وتحميلها
if 'final_df' in st.session_state:
    df = st.session_state.final_df
    st.dataframe(df, use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    st.download_button(
        label="📥 تحميل النتائج كملف Excel",
        data=output.getvalue(),
        file_name="ClikPlus_Extraction.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
