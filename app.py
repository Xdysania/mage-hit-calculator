from io import BytesIO

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

st.set_page_config(page_title="设计走查工具", layout="wide")
st.title("设计走查工具")
st.caption("上传设计稿截图 + 输入线上页面链接，自动输出差异标注。")


def screenshot_page(url: str, width: int = 1440):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        st.error("未检测到 playwright，请先安装并执行浏览器安装命令。")
        st.code("pip install playwright\npython -m playwright install chromium", language="bash")
        return None

    with sync_playwright() as p:
        launch_errors = []
        browser = None
        launch_strategies = [
            {"kwargs": {"headless": True, "args": ["--disable-dev-shm-usage"]}, "name": "chromium-default"},
            {"kwargs": {"headless": True, "channel": "chrome", "args": ["--disable-dev-shm-usage"]}, "name": "chromium-channel-chrome"},
        ]
        for strategy in launch_strategies:
            try:
                browser = p.chromium.launch(**strategy["kwargs"])
                break
            except Exception as e:
                launch_errors.append(f"{strategy['name']}: {e}")
                browser = None

        if browser is None:
            st.error("浏览器内核启动失败，请先安装 Google Chrome 后重试。")
            st.code("open -a \"Google Chrome\"", language="bash")
            st.caption("启动日志：" + " | ".join(launch_errors[-2:]))
            return None

        try:
            page = browser.new_page(viewport={"width": width, "height": 1200})
            page.goto(url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(1200)
            raw = page.screenshot(full_page=True)
            return Image.open(BytesIO(raw)).convert("RGB")
        finally:
            browser.close()


def classify_severity(area_ratio: float):
    if area_ratio >= 0.03:
        return "高", (255, 0, 0)   # 红
    if area_ratio >= 0.01:
        return "中", (255, 200, 0)  # 黄
    return "低", (30, 144, 255)     # 蓝


def compare_images(design_img: Image.Image, page_img: Image.Image):
    # 对齐到页面截图尺寸，保证长图也能完整比对
    target_w, target_h = page_img.size
    design_resized = design_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    a = np.array(design_resized)
    b = np.array(page_img)
    diff = cv2.absdiff(a, b)
    gray = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 35, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    page_area = float(target_w * target_h)
    issues = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 700:
            continue
        ratio = area / page_area
        severity, color = classify_severity(ratio)
        issues.append({"bbox": (x, y, w, h), "area": area, "ratio": ratio, "severity": severity, "color": color})

    issues.sort(key=lambda i: i["ratio"], reverse=True)

    annotated = page_img.copy()
    draw = ImageDraw.Draw(annotated)
    for i, issue in enumerate(issues, 1):
        x, y, w, h = issue["bbox"]
        color = issue["color"]
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x + 4, max(0, y - 18)), f"#{i} {issue['severity']}", fill=color)

    return design_resized, annotated, issues


left, right = st.columns(2)
with left:
    design_file = st.file_uploader("设计稿截图", type=["png", "jpg", "jpeg", "webp"])
with right:
    page_url = st.text_input("页面链接", placeholder="https://example.com")

run = st.button("开始走查", type="primary", disabled=not (design_file and page_url.strip()))

if run:
    with st.spinner("正在截图并比对，请稍等..."):
        try:
            design_img = Image.open(design_file).convert("RGB")
            page_img = screenshot_page(page_url.strip())
            if page_img is None:
                st.stop()
            design_aligned, annotated, issues = compare_images(design_img, page_img)
        except Exception as e:
            st.error(f"执行失败：{e}")
            st.stop()

    st.success(f"比对完成，共发现疑似差异区域 {len(issues)} 处。")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("设计稿（对齐后）")
        st.image(design_aligned, use_container_width=True)
    with c2:
        st.subheader("页面走查标注图")
        st.image(annotated, use_container_width=True)

    st.subheader("问题列表（按优先级）")
    if not issues:
        st.write("未发现明显差异区域。")
    else:
        for idx, issue in enumerate(issues, 1):
            x, y, w, h = issue["bbox"]
            st.write(
                f"#{idx} | {issue['severity']} | 位置(x={x}, y={y}) | 尺寸({w}x{h}) | 影响占比 {issue['ratio'] * 100:.2f}%"
            )
