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


# 메뉴 선택 목록
menu_options = ["전체 메뉴"] + sorted(menu_counts.keys())

# 요약 정보
st.markdown(
    f"""
**급식 일수:** {len(baskets):,}일　|　
**메뉴 종류 수:** {len(menu_counts):,}종　|　
**함께 나온 적이 있는 메뉴 쌍의 수:** {len(pair_counts):,}쌍
"""
)

st.divider()

# 검색 및 정렬 옵션
control_col1, control_col2 = st.columns([2, 1])

with control_col1:
    selected_menu = st.selectbox(
        "메뉴 선택",
        options=menu_options,
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


# 정렬 기준 설정
sort_column = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}[sort_label]


# 선택한 메뉴에 해당하는 규칙만 필터링
filtered_df = rules_df.copy()

if selected_menu != "전체 메뉴":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
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


# 연관 규칙 표
st.subheader("메뉴 연관 규칙")

st.caption(
    "지지도 = 두 메뉴가 함께 나온 일수 ÷ 전체 급식 일수 · "
    "신뢰도 = 조건 메뉴가 나온 날 중 결과 메뉴도 나온 비율 · "
    "향상도 = 신뢰도 ÷ 결과 메뉴의 출현 비율"
)

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

    # 향상도 상위 10개 그래프
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


st.caption(
    "※ 동시 횟수는 두 메뉴가 같은 날 나온 횟수입니다. "
    "메뉴 쌍의 수는 방향을 구분하지 않은 고유한 쌍의 개수이며, "
    "표의 규칙은 조건과 결과의 방향을 각각 바꾸어 표시합니다."
)

