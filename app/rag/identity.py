"""从 Markdown 自身推导文档身份和检索别名。"""

import re
from typing import Iterable, Tuple


_CARRIERS = ("中国电信", "中国联通", "中国移动", "中国广电", "电信", "联通", "移动", "广电")
_REGIONS = (
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
)


def normalize_identity_text(value: str) -> str:
    """用于别名匹配；忽略大小写、空白和标点。"""
    return "".join(re.findall(r"[a-z0-9\u3400-\u9fff]+", value.lower()))


def normalize_aliases(values: Iterable[str] | str | None) -> Tuple[str, ...]:
    if not values:
        return ()
    candidates = values.split(",") if isinstance(values, str) else values
    result: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        alias = str(value).strip()
        key = normalize_identity_text(alias)
        if alias and key and key not in seen:
            seen.add(key)
            result.append(alias)
    return tuple(result)


def derive_document_aliases(title: str, doc_id: str = "") -> Tuple[str, ...]:
    """为商品标题生成克制的高精度别名，避免产生“联通卡”这类宽泛名称。"""
    clean_title = re.sub(r"【[^】]*】|\[[^]]*]", "", title).strip()
    prefix_match = re.match(r"(.+?)(?=\d)", clean_title)
    product_name = (prefix_match.group(1) if prefix_match else clean_title).strip(" -—：:")
    aliases: list[str] = [title, clean_title, product_name]

    carrier = next((value for value in _CARRIERS if value in product_name), "")
    short_carrier = carrier.removeprefix("中国")
    region = next((value for value in _REGIONS if product_name.startswith(value)), "")

    if product_name.endswith("卡") and short_carrier and product_name.startswith(short_carrier):
        short_name = product_name[len(short_carrier):]
        if len(normalize_identity_text(short_name)) >= 2:
            aliases.append(short_name)

    if region and short_carrier:
        aliases.extend((f"{region}{short_carrier}卡", f"{region}卡", f"{short_carrier}{region}卡"))

    data_match = re.search(r"(\d+)\s*[gG]", clean_title)
    if data_match and short_carrier:
        data = f"{data_match.group(1)}G"
        aliases.append(f"{product_name}{data}")
        if region:
            aliases.extend((f"{short_carrier}{data}", f"{region}{data}卡"))

    if doc_id:
        aliases.append(doc_id)
    return normalize_aliases(aliases)
