from pathlib import Path

import pandas as pd
import json

import matplotlib
matplotlib.use("Agg")  # 不弹窗，直接存图
import matplotlib.pyplot as plt

# 中文正常显示
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "movies_sample.csv"
IMG_DIR = BASE_DIR / "images"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    return df

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """清洗数据：
    TODO：
      1. 删除完全重复的行（drop_duplicates）
      2. 处理缺失值：评分用中位数填充、类型/国家可填“未知”、缺失过多的行可删除
      3. 类型转换：上映年份转 int，评分转 float
      4. 剔除异常值：评分必须在 0~10、上映年份在 1900~当年
    返回清洗后的 DataFrame
    """
    # 1. 去重
    df = df.drop_duplicates()

    # 2. 缺失值：关键列缺失 → 删行；其余按 TODO 填充
    df = df.dropna(subset=["release_date"])
    df["vote_average"] = df["vote_average"].fillna(df["vote_average"].median())
    df["genres"] = df["genres"].fillna("未知")
    df["production_countries"] = df["production_countries"].fillna("未知")

    # 3. 类型转换
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["year"] = df["release_date"].dt.year
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    df["vote_average"] = df["vote_average"].astype(float)

    # 4. 异常值
    df = df[df["vote_average"].between(0, 10)]
    df = df[df["year"].between(1900, 2026)]

    #避免下面两个函数出错
    df = df[df["vote_count"] > 0]  # 62 部"假 0 分"电影
    df = df[df["runtime"].between(1, 600)]  # 22 部"0 分钟"电影
    df = df[df["status"] == "Released"]  # 8 部未上映

    return df

def _names(s):
    """把 '[{"id":28,"name":"Action"}]' 解析成 ['Action']"""
    try:
        return [d["name"] for d in json.loads(s)]
    except (json.JSONDecodeError, TypeError):
        return []

def analyze(df: pd.DataFrame) -> dict:
    """分组统计：

    TODO：
      1. 按年份统计电影数量与平均评分（groupby + agg）
      2. 按类型统计平均评分，排序取 Top10
      3. 按国家统计电影产量，取 Top5
    建议把统计结果 return 出去，供画图复用
    """
    # 1. 按年份
    by_year = (df.groupby("year")
                 .agg(movie_count=("title", "count"),
                      avg_rating=("vote_average", "mean"))
                 .round(2))

    # 2. 按类型（先解析 JSON，再 explode 把一行拆成多行）
    genre_df = df.assign(genre=df["genres"].apply(_names)).explode("genre")
    genre_df = genre_df[genre_df["genre"].notna()]
    by_genre = (genre_df.groupby("genre")
                .agg(movie_count=("title", "count"),
                     avg_rating=("vote_average", "mean"))
                .round(2))
    by_genre = by_genre[by_genre["movie_count"] >= 50]
    by_genre = by_genre.sort_values("avg_rating", ascending=False).head(10)

    # 3. 按国家
    country_df = df.assign(country=df["production_countries"].apply(_names)).explode("country")
    country_df = country_df[country_df["country"].notna()]
    by_country = (country_df.groupby("country")
                  .agg(movie_count=("title", "count"))
                  .sort_values("movie_count", ascending=False).head(5))

    return {"by_year": by_year, "by_genre": by_genre, "by_country": by_country}


def visualize(df: pd.DataFrame, stats: dict) -> None:
    """画 3 张图并保存到 images/

    TODO：
      1. 评分分布直方图（plt.hist）
      2. 每年平均评分趋势折线图（plt.plot，x 轴按年份升序）
      3. Top10 类型平均评分横向柱状图（plt.barh）
    每张图都要有标题、轴标签，并用 plt.savefig(IMG_DIR / "xxx.png", dpi=150)
    """
    # 1. 评分分布直方图
    plt.figure(figsize=(8, 5))
    plt.hist(df["vote_average"], bins=20, range=(0, 10), edgecolor="black")
    plt.title(f"电影评分分布（n={len(df)}）")
    plt.xlabel("评分")
    plt.ylabel("电影数量")
    plt.savefig(IMG_DIR / "rating_dist.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 2. 年度平均评分趋势（只保留样本≥10部的年份）
    trend = stats["by_year"]
    trend = trend[trend["movie_count"] >= 10]
    plt.figure(figsize=(10, 5))
    plt.plot(trend.index, trend["avg_rating"], marker="o", linewidth=1.5)
    plt.title("每年平均评分趋势（样本≥10部）")
    plt.xlabel("年份")
    plt.ylabel("平均评分")
    plt.grid(alpha=0.3)
    plt.savefig(IMG_DIR / "yearly_trend.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 3. Top10 类型平均评分（barh 要升序，最大值才在最上面）
    top10 = stats["by_genre"].sort_values("avg_rating")
    plt.figure(figsize=(9, 5))
    plt.barh(top10.index, top10["avg_rating"])
    plt.title("平均评分最高的 10 个类型（样本≥50部）")
    plt.xlabel("平均评分")
    plt.ylabel("类型")
    for i, (v, n) in enumerate(zip(top10["avg_rating"], top10["movie_count"])):
        plt.text(v + 0.02, i, f"{v:.2f} ({n}部)", va="center", fontsize=8)
    plt.savefig(IMG_DIR / "genre_top10.png", dpi=150, bbox_inches="tight")
    plt.close()



def main() -> None:
    IMG_DIR.mkdir(exist_ok=True)
    df = load_data()
    df = clean_data(df)
    stats = analyze(df)
    visualize(df, stats)



if __name__ == "__main__":
    main()

