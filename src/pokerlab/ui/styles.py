"""Единая CSS-тема для всего приложения."""

from __future__ import annotations

import streamlit as st


_CSS = """
<style>
/* ============================================================
   ОСНОВА
   ============================================================ */
.stApp {
    background: #f5f7fa;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100%;
    margin: 0 auto;
}

/* ============================================================
   ЗАГОЛОВКИ
   ============================================================ */
h1 {
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.5px;
    padding-bottom: 0;
    border-bottom: none;
    margin-top: 8px !important;
    margin-bottom: 24px !important;
    text-align: center;
}
h2 {
    font-size: 20px !important;
    font-weight: 600 !important;
    color: #1e293b !important;
    margin-top: 32px !important;
    margin-bottom: 16px !important;
}
h3 {
    font-size: 17px !important;
    font-weight: 600 !important;
    color: #334155 !important;
    margin-top: 24px !important;
    margin-bottom: 12px !important;
    text-align: center !important;
}

/* ============================================================
   ВЕРХНИЕ ВКЛАДКИ — 6 прямоугольников 2:1, тёмно-серые
   ============================================================ */
div[role="tablist"],
[data-baseweb="tab-list"] {
    display: grid !important;
    grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
    gap: 12px !important;
    width: 100% !important;
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 0 24px 0 !important;
    border: none !important;
    background: transparent !important;
    box-sizing: border-box !important;
    flex-wrap: nowrap !important;
    align-items: start !important;
}

div[role="tablist"] button[role="tab"],
[data-baseweb="tab-list"] button[role="tab"],
button[data-baseweb="tab"],
button[role="tab"][data-baseweb],
div[role="tablist"] > div > button,
[data-testid="stTab"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    aspect-ratio: 2 / 1 !important;
    height: auto !important;
    min-height: 0 !important;
    padding: 8px 8px !important;
    margin: 0 !important;
    background: linear-gradient(145deg, #2d3748 0%, #1a202c 100%) !important;
    border: 1px solid #1a202c !important;
    border-radius: 14px !important;
    box-sizing: border-box !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow:
        0 2px 4px rgba(15, 23, 42, 0.15),
        0 8px 20px rgba(15, 23, 42, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    cursor: pointer !important;
    overflow: hidden !important;
    outline: none !important;
    flex: none !important;
    position: relative !important;
    transform: none !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    color: #cbd5e1 !important;
    letter-spacing: -0.2px !important;
    line-height: 1.2 !important;
    white-space: normal !important;
    text-decoration: none !important;
}

div[role="tablist"] button[role="tab"]::before,
[data-baseweb="tab-list"] button[role="tab"]::before,
button[data-baseweb="tab"]::before,
[data-testid="stTab"]::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(255,255,255,0.15) 50%,
        transparent 100%);
    pointer-events: none;
}

div[role="tablist"] button[role="tab"] *,
[data-baseweb="tab-list"] button[role="tab"] *,
button[data-baseweb="tab"] *,
button[role="tab"][data-baseweb] *,
[data-testid="stTab"] * {
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    color: inherit !important;
    letter-spacing: -0.2px !important;
    line-height: 1.2 !important;
    text-align: center !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    display: inline-block !important;
    white-space: normal !important;
}

div[role="tablist"] button[role="tab"] p,
[data-baseweb="tab-list"] button[role="tab"] p,
button[data-baseweb="tab"] p,
[data-testid="stTab"] p {
    font-size: 16px !important;
    font-weight: 600 !important;
    color: inherit !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    text-align: center !important;
}

div[role="tablist"] button[role="tab"] [data-testid="stMarkdownContainer"],
[data-baseweb="tab-list"] button[role="tab"] [data-testid="stMarkdownContainer"],
[data-testid="stTab"] [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
    padding: 0 !important;
    margin: 0 0 8px 0 !important;
}

div[role="tablist"] button[role="tab"]:hover,
[data-baseweb="tab-list"] button[role="tab"]:hover,
button[data-baseweb="tab"]:hover,
[data-testid="stTab"]:hover {
    background: linear-gradient(145deg, #4a5568 0%, #2d3748 100%) !important;
    border-color: #4a5568 !important;
    box-shadow:
        0 6px 12px rgba(15, 23, 42, 0.2),
        0 16px 32px rgba(15, 23, 42, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.12) !important;
    transform: translateY(-3px) !important;
    color: #ffffff !important;
}
div[role="tablist"] button[role="tab"]:hover *,
[data-baseweb="tab-list"] button[role="tab"]:hover *,
button[data-baseweb="tab"]:hover *,
[data-testid="stTab"]:hover * {
    color: #ffffff !important;
}

div[role="tablist"] button[role="tab"][aria-selected="true"],
[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"],
[data-testid="stTab"][aria-selected="true"] {
    background: linear-gradient(145deg, #10b981 0%, #059669 100%) !important;
    border-color: #059669 !important;
    box-shadow:
        0 6px 16px rgba(16, 185, 129, 0.35),
        0 16px 40px rgba(16, 185, 129, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
    transform: translateY(-3px) !important;
    color: #ffffff !important;
}
div[role="tablist"] button[role="tab"][aria-selected="true"] *,
[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] *,
button[data-baseweb="tab"][aria-selected="true"] *,
[data-testid="stTab"][aria-selected="true"] * {
    color: #ffffff !important;
    font-weight: 700 !important;
}

div[role="tablist"] button[role="tab"][aria-selected="true"]::before,
[data-testid="stTab"][aria-selected="true"]::before {
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(255,255,255,0.5) 50%,
        transparent 100%);
}

div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"],
div[data-baseweb="tab-list"] > div[role="presentation"] {
    display: none !important;
}

/* ============================================================
   МЕТРИКИ
   ============================================================ */
[data-testid="stMetric"] {
    background: #ffffff;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    border: 1px solid #e5e7eb;
    transition: all 0.15s ease;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    border-color: #d1d5db;
}
[data-testid="stMetricLabel"] {
    font-size: 12px !important;
    color: #64748b !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    font-size: 24px !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.3px;
}

/* ============================================================
   HANDS — заголовок, счётчик, подпись слайдера
   ============================================================ */
.hands-title {
    text-align: center;
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.5px;
    margin-top: -16px;
    margin-bottom: 2px;
    line-height: 1.1;
}

.slider-label-centered {
    text-align: center;
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.3px;
    margin-top: 6px;
    margin-bottom: 2px;
}

.hands-count {
    text-align: center;
    font-size: 14px;
    color: #64748b;
    margin-top: 4px;
    margin-bottom: 20px;
    font-weight: 500;
}
.hands-count b {
    color: #0f172a;
    font-weight: 700;
}

/* ============================================================
   ТАБЛИЦЫ — жирные заголовки, читаемые строки
   ============================================================ */
[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    background: #ffffff;
}

[data-testid="stDataFrame"] div[role="gridcell"],
[data-testid="stDataFrame"] div[role="columnheader"],
[data-testid="stDataFrame"] div[role="columnheader"] *,
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] [role="columnheader"] *,
[data-testid="stDataFrame"] .col-header,
[data-testid="stDataFrame"] .gdg-header {
    font-size: 14px !important;
    padding: 8px 10px !important;
}

[data-testid="stDataFrame"] div[role="columnheader"],
[data-testid="stDataFrame"] div[role="columnheader"] *,
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] [role="columnheader"] *,
[data-testid="stDataFrame"] [data-testid="stDataFrameColumnHeader"],
[data-testid="stDataFrame"] [data-testid="stDataFrameColumnHeader"] * {
    font-weight: 900 !important;
    font-size: 12.5px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.7px !important;
    color: #0f172a !important;
    background: #f1f5f9 !important;
    -webkit-text-stroke: 0.3px #0f172a !important;
}

[data-testid="stDataFrame"] div[role="columnheader"] {
    border-bottom: 2px solid #cbd5e1 !important;
}

[data-testid="stDataFrame"] div[role="row"]:first-of-type div[role="gridcell"] {
    font-weight: 700 !important;
    color: #0f172a !important;
}

[data-testid="stDataFrame"] div[role="row"]:hover {
    background: #f0fdf4 !important;
}
[data-testid="stDataFrame"] div[role="row"]:nth-child(even) {
    background: #fafbfc;
}

[data-testid="stDataFrame"] > div {
    border-radius: 14px;
}

/* ============================================================
   ГРАФИКИ
   ============================================================ */
.js-plotly-plot {
    border-radius: 12px;
    background: #ffffff;
    padding: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    border: 1px solid #e5e7eb;
}

/* ============================================================
   КНОПКИ — изумрудные
   ============================================================ */
.stButton > button {
    background: linear-gradient(180deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 14px;
    box-shadow: 0 1px 3px rgba(16, 185, 129, 0.3);
    transition: all 0.15s ease;
}
.stButton > button:hover {
    background: linear-gradient(180deg, #059669 0%, #047857 100%);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    transform: translateY(-1px);
}

/* ============================================================
   ALERT
   ============================================================ */
.stAlert {
    border-radius: 10px;
}

/* ============================================================
   DIVIDER
   ============================================================ */
hr {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 28px 0;
}

/* ============================================================
   CAPTION
   ============================================================ */
[data-testid="stCaptionContainer"] {
    color: #64748b;
    font-size: 13px;
}

/* ============================================================
   RADIO (период, режим) — общий стиль
   ============================================================ */
.stRadio > label {
    color: #475569 !important;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stRadio > div[role="radiogroup"] {
    gap: 6px;
    flex-wrap: wrap;
}
.stRadio > div[role="radiogroup"] > label {
    padding: 8px 18px;
    border-radius: 8px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    color: #475569;
    font-weight: 500;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s ease;
}
.stRadio > div[role="radiogroup"] > label:hover {
    background: #f9fafb;
    border-color: #cbd5e1;
}
.stRadio > div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    border-color: #059669;
    color: #ffffff !important;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);
}
.stRadio input[type="radio"] {
    display: none;
}

/* ============================================================
   КАРТОЧКА ФИЛЬТРОВ
   ============================================================ */
.st-key-filters_ov,
.st-key-filters_hn {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 16px !important;
    padding: 32px 24px 20px 24px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    margin-bottom: 12px !important;
    margin-top: -8px !important;
}

[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
    gap: 4px !important;
}

.filter-card-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    padding: 0 0 14px 0;
    margin: -20px 0 8px 0;
    border-bottom: 1px solid #f1f5f9;
}

.filter-card-icon {
    width: 40px;
    height: 40px;
    border-radius: 11px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    box-shadow: 0 3px 10px rgba(16, 185, 129, 0.35);
    flex-shrink: 0;
}

.filter-card-title-text {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.5px;
    line-height: 1.1;
}

/* Компактные лейблы фильтров */
div[data-testid="stHorizontalBlock"] .stSlider > label,
div[data-testid="stHorizontalBlock"] .stMultiSelect > label,
div[data-testid="stHorizontalBlock"] .stRadio > label {
    font-size: 10px !important;
    color: #64748b !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.7px !important;
    margin-bottom: 4px !important;
}

div[data-testid="stHorizontalBlock"] .stSlider {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
div[data-testid="stSlider"] [data-testid="stTickBarMin"],
div[data-testid="stSlider"] [data-testid="stTickBarMax"] {
    font-size: 10px !important;
    color: #94a3b8 !important;
}

[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border-color: #e2e8f0 !important;
    border-radius: 8px !important;
    min-height: 34px !important;
    font-size: 12px !important;
}
[data-baseweb="select"] > div:hover {
    border-color: #cbd5e1 !important;
}
[data-baseweb="select"] > div:focus-within {
    border-color: #10b981 !important;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15) !important;
}

span[data-baseweb="tag"] {
    background-color: #ecfdf5 !important;
    color: #047857 !important;
    border: 1px solid #a7f3d0 !important;
    border-radius: 5px !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    padding: 1px 6px !important;
    margin: 1px !important;
    height: 22px !important;
}
span[data-baseweb="tag"] * {
    color: #047857 !important;
    background: transparent !important;
}
span[data-baseweb="tag"] svg {
    fill: #047857 !important;
    width: 12px !important;
    height: 12px !important;
}

div[data-testid="stHorizontalBlock"] .stRadio > div[role="radiogroup"] {
    gap: 4px !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
}
div[data-testid="stHorizontalBlock"] .stRadio > div[role="radiogroup"] > label {
    padding: 4px 10px !important;
    font-size: 11px !important;
    border-radius: 6px !important;
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    margin: 0 !important;
    min-height: 26px !important;
    color: #64748b !important;
    font-weight: 600 !important;
}
div[data-testid="stHorizontalBlock"] .stRadio > div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    border-color: #059669 !important;
    color: #ffffff !important;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3) !important;
}

[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background-color: #10b981 !important;
    border-color: #10b981 !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div:first-child {
    background: #10b981 !important;
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)