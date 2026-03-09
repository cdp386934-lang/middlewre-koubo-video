#!/usr/bin/env python3
"""
测试 CapCut-mate API 调用流程
"""

import requests
import json


def test_capcut_api():
    """测试完整的 API 调用流程"""
    api_url = "http://localhost:30000"

    print("=" * 60)
    print("测试 CapCut-mate API 调用流程")
    print("=" * 60)

    # 1. 创建草稿
    print("\n[步骤 1] 创建草稿...")
    response = requests.post(
        f"{api_url}/openapi/capcut-mate/v1/create_draft",
        json={"width": 960, "height": 544}
    )
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if result.get("code") != 0:
        print(f"❌ 创建草稿失败: {result.get('message')}")
        return

    draft_url = result.get("draft_url")
    print(f"✅ 草稿创建成功")
    print(f"   draft_url: {draft_url}")

    # 2. 保存草稿
    print("\n[步骤 2] 保存草稿...")
    response = requests.post(
        f"{api_url}/openapi/capcut-mate/v1/save_draft",
        json={"draft_url": draft_url}
    )
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if result.get("code") != 0:
        print(f"❌ 保存草稿失败: {result.get('message')}")
        print(f"   错误代码: {result.get('code')}")
        return

    print(f"✅ 草稿保存成功")

    # 3. 获取草稿信息
    print("\n[步骤 3] 获取草稿信息...")
    draft_id = draft_url.split("draft_id=")[1]
    response = requests.get(
        f"{api_url}/openapi/capcut-mate/v1/get_draft",
        params={"draft_id": draft_id}
    )
    result = response.json()

    if result.get("code") != 0:
        print(f"❌ 获取草稿信息失败: {result.get('message')}")
        return

    files = result.get("files", [])
    print(f"✅ 草稿包含 {len(files)} 个文件")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_capcut_api()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
