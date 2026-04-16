"""
API 数据源管理模块
支持用户自定义API接口，批量获取数据并向量化入库
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

API_SOURCES_FILE = Path("data/api_sources.json")


@dataclass
class ApiSourceConfig:
    """API数据源配置"""
    source_id: str
    name: str                    # 数据源名称
    source_type: str             # "single" | "list_detail"

    # 单接口模式
    api_url: str = ""            # API地址
    content_path: str = ""       # 内容字段路径，如 "results.content"

    # 列表+详情模式
    list_api_url: str = ""       # 列表接口地址
    list_id_path: str = ""       # 列表中ID字段路径，如 "results[].id"
    detail_api_url: str = ""     # 详情接口地址模板，如 "https://api.com/detail/{id}"
    detail_content_path: str = "" # 详情内容字段路径

    # 数据转换（可选）
    transform_script: str = ""   # Python转换脚本，用于处理列表数据（如树形结构扁平化）

    # HTTP配置
    method: str = "GET"          # HTTP方法
    headers: dict[str, str] = field(default_factory=dict)  # 请求头
    timeout: int = 30            # 超时时间（秒）

    # 状态
    enabled: bool = True
    last_sync_time: Optional[str] = None
    last_sync_count: int = 0


def _load_api_sources() -> dict:
    """加载API数据源配置"""
    if API_SOURCES_FILE.exists():
        try:
            return json.loads(API_SOURCES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"sources": []}
    return {"sources": []}


def _save_api_sources(data: dict) -> None:
    """保存API数据源配置"""
    API_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_SOURCES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_api_sources() -> list[dict]:
    """获取所有API数据源配置"""
    data = _load_api_sources()
    return data.get("sources", [])


def add_api_source(config: ApiSourceConfig) -> ApiSourceConfig:
    """添加新的API数据源"""
    data = _load_api_sources()
    sources = data.get("sources", [])

    # 检查名称是否重复
    if any(s["name"] == config.name for s in sources):
        raise ValueError(f"数据源名称 '{config.name}' 已存在")

    sources.append(asdict(config))
    data["sources"] = sources
    _save_api_sources(data)
    return config


def update_api_source(source_id: str, updates: dict) -> bool:
    """更新API数据源配置"""
    data = _load_api_sources()
    sources = data.get("sources", [])

    for source in sources:
        if source["source_id"] == source_id:
            source.update(updates)
            _save_api_sources(data)
            return True
    return False


def delete_api_source(source_id: str) -> bool:
    """删除API数据源"""
    data = _load_api_sources()
    sources = data.get("sources", [])
    new_sources = [s for s in sources if s["source_id"] != source_id]

    if len(new_sources) == len(sources):
        return False

    data["sources"] = new_sources
    _save_api_sources(data)
    return True


def _get_nested_value(data: Any, path: str) -> Any:
    """
    从嵌套数据结构中提取值
    支持路径格式：
    - "field" - 简单字段
    - "field.subfield" - 嵌套字段
    - "field[].id" - 数组中的字段（返回列表）
    - "field[0].id" - 数组索引
    """
    if not path:
        return data

    parts = path.split(".")
    current = data

    for part in parts:
        if not part:
            continue

        # 处理数组语法 field[] 或 field[0]
        if "[" in part and "]" in part:
            field_name = part[:part.index("[")]
            index_part = part[part.index("[") + 1:part.index("]")]

            # 获取字段
            if field_name:
                current = current.get(field_name) if isinstance(current, dict) else None

            if current is None:
                return None

            # 处理索引
            if index_part == "":  # field[] - 返回所有元素
                if not isinstance(current, list):
                    return None
                # 继续处理后续路径
                continue
            else:  # field[0] - 返回指定索引
                try:
                    idx = int(index_part)
                    current = current[idx] if isinstance(current, list) and len(current) > idx else None
                except (ValueError, IndexError, TypeError):
                    return None
        else:
            # 普通字段访问
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # 如果当前是列表，对每个元素提取字段
                current = [item.get(part) if isinstance(item, dict) else None for item in current]
                current = [x for x in current if x is not None]
            else:
                return None

        if current is None:
            return None

    return current


def _apply_transform(data: Any, script: str) -> Any:
    """
    应用Python转换脚本处理数据

    脚本中可用变量：
    - data: 原始数据
    - result: 转换后的结果（需要设置）

    示例脚本（树形结构扁平化）：
    ```python
    def flatten_tree(node, result_list):
        result_list.append(node)
        if 'children' in node and node['children']:
            for child in node['children']:
                flatten_tree(child, result_list)

    result = []
    if isinstance(data, list):
        for item in data:
            flatten_tree(item, result)
    else:
        flatten_tree(data, result)
    ```
    """
    if not script or not script.strip():
        return data

    try:
        # 创建执行环境
        exec_globals = {
            '__builtins__': {
                'isinstance': isinstance,
                'list': list,
                'dict': dict,
                'str': str,
                'int': int,
                'float': float,
                'len': len,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'sorted': sorted,
                'sum': sum,
                'min': min,
                'max': max,
                'any': any,
                'all': all,
                'print': print,
            },
            'data': data,
            'result': None,
        }

        # 执行转换脚本（函数定义和调用都在同一个命名空间）
        exec(script, exec_globals)

        # 返回转换结果
        if exec_globals.get('result') is not None:
            return exec_globals['result']
        else:
            logger.warning("[Transform] 脚本未设置 result 变量，返回原始数据")
            return data

    except Exception as e:
        logger.error(f"[Transform] 转换脚本执行失败: {e}")
        raise ValueError(f"数据转换失败: {e}")


async def fetch_api_data(config: ApiSourceConfig) -> list[str]:
    """
    从API获取数据
    返回: markdown文本列表
    """
    results: list[str] = []

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        if config.source_type == "single":
            # 单接口模式
            response = await client.request(
                method=config.method,
                url=config.api_url,
                headers=config.headers,
            )
            response.raise_for_status()
            data = response.json()

            content = _get_nested_value(data, config.content_path)
            if content:
                if isinstance(content, list):
                    results.extend([str(item) for item in content if item])
                else:
                    results.append(str(content))

        elif config.source_type == "list_detail":
            # 列表+详情模式
            # 1. 获取列表
            list_response = await client.request(
                method=config.method,
                url=config.list_api_url,
                headers=config.headers,
            )
            list_response.raise_for_status()
            list_data = list_response.json()

            # 2. 应用转换脚本（如果有）
            if config.transform_script:
                logger.info(f"[API Source] 应用数据转换脚本")
                list_data = _apply_transform(list_data, config.transform_script)

            # 3. 提取ID列表
            ids = _get_nested_value(list_data, config.list_id_path)
            if not ids:
                logger.warning(f"[API Source] 未从列表接口提取到ID: {config.name}")
                return results

            if not isinstance(ids, list):
                ids = [ids]

            logger.info(f"[API Source] 从列表接口获取到 {len(ids)} 个ID")

            # 4. 逐个获取详情
            for item_id in ids:
                try:
                    detail_url = config.detail_api_url.replace("{id}", str(item_id))
                    detail_response = await client.request(
                        method=config.method,
                        url=detail_url,
                        headers=config.headers,
                    )
                    detail_response.raise_for_status()
                    detail_data = detail_response.json()

                    content = _get_nested_value(detail_data, config.detail_content_path)
                    if content:
                        results.append(str(content))
                except Exception as e:
                    logger.error(f"[API Source] 获取详情失败 (ID={item_id}): {e}")
                    continue

    return results


async def sync_api_source(source_id: str) -> dict:
    """
    同步API数据源
    返回: {"success": bool, "count": int, "doc_ids": list, "error": str}
    """
    from datetime import datetime
    from rag import ingest_document

    # 加载配置
    sources = get_api_sources()
    config_dict = next((s for s in sources if s["source_id"] == source_id), None)
    if not config_dict:
        return {"success": False, "count": 0, "doc_ids": [], "error": "数据源不存在"}

    config = ApiSourceConfig(**config_dict)

    if not config.enabled:
        return {"success": False, "count": 0, "doc_ids": [], "error": "数据源已禁用"}

    try:
        # 获取数据
        logger.info(f"[API Source] 开始同步: {config.name}")
        contents = await fetch_api_data(config)

        if not contents:
            return {"success": False, "count": 0, "doc_ids": [], "error": "未获取到任何内容"}

        logger.info(f"[API Source] 获取到 {len(contents)} 条内容")

        # 将每条内容作为独立文档入库
        doc_ids = []
        for idx, content in enumerate(contents):
            try:
                # 生成文件名
                filename = f"{config.name}_{idx + 1}.md"
                file_bytes = content.encode("utf-8")

                # 入库（不立即向量化，返回后由后台任务处理）
                doc = ingest_document(file_bytes, filename, embed=False)
                doc_ids.append(doc.doc_id)
            except Exception as e:
                logger.error(f"[API Source] 入库失败 (索引={idx}): {e}")
                continue

        # 更新同步状态
        update_api_source(source_id, {
            "last_sync_time": datetime.now().isoformat(),
            "last_sync_count": len(doc_ids),
        })

        return {
            "success": True,
            "count": len(doc_ids),
            "doc_ids": doc_ids,
            "error": None,
        }

    except httpx.HTTPError as e:
        error_msg = f"HTTP请求失败: {e}"
        logger.error(f"[API Source] {error_msg}")
        return {"success": False, "count": 0, "doc_ids": [], "error": error_msg}
    except Exception as e:
        error_msg = f"同步失败: {e}"
        logger.error(f"[API Source] {error_msg}")
        return {"success": False, "count": 0, "doc_ids": [], "error": error_msg}
