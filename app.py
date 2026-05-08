import pathlib
import streamlit as st


st.set_page_config(page_title="本地工具入口", layout="wide")
st.title("本地工具入口")
st.write("Streamlit 已成功启动。")

calc_path = pathlib.Path(__file__).with_name("mage-hit-calculator.html")
if calc_path.exists():
    st.success(f"已检测到计算器文件：`{calc_path}`")
    st.info("请直接在浏览器中打开该 HTML 文件，或用本地服务器访问。")
else:
    st.warning("未检测到 `mage-hit-calculator.html`。")

st.code(
    "cd \"/Users/fadada/Desktop/AI代码存放处/design-review-ai\" && "
    "python3 -m http.server 9000",
    language="bash",
)
st.write("然后访问：`http://localhost:9000/mage-hit-calculator.html`")
