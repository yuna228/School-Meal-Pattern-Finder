
import re
from collections import Counter
from itertools import combinations

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_URL = (
    "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/"
    "songtan_meals_184.csv"
)

st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍱",
    layout="wide",
)

st.title("🍱 급식 규칙 찾기")
st.write(
    "송탄고 중식 데이터를 이용해 같은 날 함께 나온 메뉴와 "
    "메뉴 사이의 연관 규칙을 찾아봅니다."
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_URL, encoding="utf-8")

    required_columns = {"날짜", "식사", "메뉴"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "CSV에 필요한 열이 없습니다: "
            + ", ".join(sorted(missing_columns))
        )

    return df


def clean_menu_name(name):
    """괄호와 괄호 안의 내용을 제거합니다."""
    name = re.sub(r"\([^)]*\)", "", str(name))
    name = re.sub(r"（[^）]*）", "", name)
    return name.strip()


@st.cache_data
def make_association_rules(df):
    """하루 식단을 장바구니 한 건으로 보고 연관 규칙을 계산합니다."""

    baskets = []
    menu_counts = Counter()
    pair_counts = Counter()

    for menu_text in df["메뉴"].fillna(""):
        # 같은 날 같은 메뉴가 중복되어도 한 번만 집계
        basket = {
            cleaned
            for raw_name in str(menu_text).split("|")
            if (cleaned := clean_menu_name(raw_name))
        }

        if not basket:
            continue

        baskets.append(basket)
        menu_counts.update(basket)

        pair_counts.update(
            combinations(sorted(basket), 2)
        )

    total_days = len(baskets)
    rules = []

    for (menu_a, menu_b), together_count in pair_counts.items():

        support = together_count / total_days

        confidence_a_b = (
            together_count / menu_counts[menu_a]
        )

        confidence_b_a = (
            together_count / menu_counts[menu_b]
        )

        support_a = menu_counts[menu_a] / total_days
        support_b = menu_counts[menu_b] / total_days

        lift_a_b = confidence_a_b / support_b
        lift_b_a = confidence_b_a / support_a

        # A → B
        rules.append({
            "조건": menu_a,
            "결과": menu_b,
            "동시": together_count,
            "지지도": support,
            "신뢰도": confidence_a_b,
            "향상도": lift_a_b,
        })

        # B → A
        rules.append({
            "조건": menu_b,
            "결과": menu_a,
            "동시": together_count,
            "지지도": support,
            "신뢰도": confidence_b_a,
            "향상도": lift_b_a,
        })

    rules_df = pd.DataFrame(
        rules,
        columns=[
            "조건",
            "결과",
            "동시",
            "지지도",
            "신뢰도",
            "향상도",
        ],
    )

    return baskets, menu_counts, pair_counts, rules_df


# 데이터 불러오기 및 분석
try:
    raw_df = load_data()

    baskets, menu_counts, pair_counts, rules_df = (
        make_association_rules(raw_df)
    )

except Exception as error:
    st.error(
        f"데이터를 불러오거나 분석하는 중 오류가 발생했습니다: {error}"
    )
    st.stop()


# 메뉴 목록
menu_options = sorted(menu_counts.keys())


# 요약 정보
st.markdown(
    f"""
**급식 일수:** {len(baskets):,}일　|　
**메뉴 종류 수:** {len(menu_counts):,}종　|　
**함께 나온 적이 있는 메뉴 쌍의 수:** {len(pair_counts):,}쌍
"""
)

st.divider()


# =====================================
# 1. 메뉴 연관 규칙
# =====================================

st.subheader("메뉴 연관 규칙")

control_col1, control_col2 = st.columns([2, 1])

with control_col1:
    selected_rule_menu = st.selectbox(
        "좁혀 보기",
        options=["전체 메뉴"] + menu_options,
        help="선택한 메뉴가 조건 또는 결과에 포함된 규칙만 표시합니다.",
    )

with control_col2:
    sort_label = st.selectbox(
        "정렬 기준",
        options=[
            "향상도 순",
            "신뢰도 순",
            "동시 순",
        ],
        index=0,
    )


# 최소 동시 일수 슬라이더
min_together = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
    help="선택한 일수보다 적게 함께 나온 규칙은 표와 그래프에서 제외합니다.",
)


# 정렬 기준
sort_column = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}[sort_label]


# 메뉴 필터
filtered_df = rules_df.copy()

if selected_rule_menu != "전체 메뉴":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_rule_menu)
        | (filtered_df["결과"] == selected_rule_menu)
    ]


# 최소 동시 일수 필터
filtered_df = filtered_df[
    filtered_df["동시"] >= min_together
]


# 정렬
filtered_df = filtered_df.sort_values(
    by=[
        sort_column,
        "신뢰도",
        "동시",
    ],
    ascending=[
        False,
        False,
        False,
    ],
).reset_index(drop=True)


# 남은 규칙 개수
st.write(
    f"**현재 표에 표시되는 규칙: {len(filtered_df):,}개**"
)


# 연관 규칙 설명
st.caption(
    "지지도 = 두 메뉴가 함께 나온 일수 ÷ 전체 급식 일수 · "
    "신뢰도 = 조건 메뉴가 나온 날 중 결과 메뉴도 나온 비율 · "
    "향상도 = 신뢰도 ÷ 결과 메뉴의 출현 비율"
)


# 연관 규칙 표
if filtered_df.empty:

    st.info("선택한 조건에 해당하는 메뉴 규칙이 없습니다.")

else:

    display_df = filtered_df.copy()

    display_df["지지도"] = display_df["지지도"].map(
        lambda value: f"{value:.3%}"
    )

    display_df["신뢰도"] = display_df["신뢰도"].map(
        lambda value: f"{value:.3%}"
    )

    display_df["향상도"] = display_df["향상도"].map(
        lambda value: f"{value:.3f}"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


    # =====================================
    # 2. 향상도 상위 10개 그래프
    # =====================================

    st.subheader("향상도 상위 10개 규칙")

    top10 = (
        filtered_df
        .sort_values(
            by=[
                "향상도",
                "신뢰도",
                "동시",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        )
        .head(10)
        .copy()
    )

    if not top10.empty:

        top10["규칙"] = (
            top10["조건"] + " → " + top10["결과"]
        )

        chart_df = top10.sort_values(
            "향상도",
            ascending=True,
        )

        fig = px.bar(
            chart_df,
            x="향상도",
            y="규칙",
            orientation="h",
            text=chart_df["향상도"].map(
                lambda value: f"{value:.2f}"
            ),
            hover_data={
                "조건": True,
                "결과": True,
                "동시": True,
                "지지도": ":.3%",
                "신뢰도": ":.3%",
                "향상도": ":.3f",
                "규칙": False,
            },
            labels={
                "향상도": "향상도",
                "규칙": "연관 규칙",
            },
            title="향상도 상위 10개",
        )

        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
        )

        fig.update_layout(
            yaxis_title="",
            xaxis_title="향상도",
            height=max(
                420,
                42 * len(chart_df) + 120,
            ),
            margin=dict(
                l=20,
                r=50,
                t=60,
                b=30,
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =====================================
# 3. 함께 나온 적 없는 짝
# =====================================

st.divider()

st.subheader("함께 나온 적 없는 짝")

st.write(
    "선택한 메뉴와 같은 날 한 번도 함께 나오지 않았지만, "
    "각각 혼자서는 10일 이상 나온 메뉴를 찾아봅니다."
)


if menu_options:

    # 위의 좁혀 보기와 독립적인 메뉴 선택 상자
    selected_absent_menu = st.selectbox(
        "함께 나온 적 없는 짝을 찾을 기준 메뉴",
        options=menu_options,
        key="absent_pair_base_menu",
        help="위의 좁혀 보기와 별도로 작동하는 메뉴 선택입니다.",
    )

    # 기준 메뉴가 나온 날짜 수
    base_menu_days = menu_counts[selected_absent_menu]


    # 함께 나온 기록이 없고 10일 이상 등장한 메뉴
    absent_menus = [
        (menu, days)
        for menu, days in menu_counts.items()
        if menu != selected_absent_menu
        and days >= 10
        and tuple(
            sorted((selected_absent_menu, menu))
        ) not in pair_counts
    ]


    # 데이터프레임 생성
    absent_df = pd.DataFrame(
        absent_menus,
        columns=[
            "함께 나온 적 없는 메뉴",
            "메뉴가 나온 날 수",
        ],
    )


    if not absent_df.empty:

        # 등장 횟수 내림차순 정렬
        absent_df = absent_df.sort_values(
            by=[
                "메뉴가 나온 날 수",
                "함께 나온 적 없는 메뉴",
            ],
            ascending=[
                False,
                True,
            ],
        ).reset_index(drop=True)


        # 기준 메뉴 출현 일수와 짝 개수
        st.write(
            f"**기준 메뉴 '{selected_absent_menu}' 출현 일수: "
            f"{base_menu_days:,}일**　|　"
            f"**함께 나온 적 없는 메뉴: "
            f"{len(absent_df):,}종**"
        )


        # 결과 표
        st.dataframe(
            absent_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.write(
            f"기준 메뉴 '{selected_absent_menu}'는 "
            f"총 {base_menu_days:,}일 나왔습니다."
        )

        st.info(
            "이 메뉴와 한 번도 함께 나오지 않았고 "
            "10일 이상 나온 다른 메뉴가 없습니다."
        )

else:

    st.info("분석할 메뉴가 없습니다.")


# =====================================
# 안내 문구
# =====================================

st.caption(
    "※ 동시 횟수는 두 메뉴가 같은 날 나온 횟수입니다. "
    "메뉴 쌍의 수는 방향을 구분하지 않은 고유한 쌍의 개수이며, "
    "표의 규칙은 조건과 결과의 방향을 각각 바꾸어 표시합니다."
)
