"""
设置服务模块

提供设置的获取和更新等业务逻辑
"""

from typing import Dict, Any, Tuple, Optional

from app.models.settings import Settings
from app.util.db import session_scope
from app.util.logger import get_logger


logger = get_logger(__name__)


class SettingsService:
    """设置服务类"""

    def _get_default_settings(self) -> Dict[str, Any]:
        """
        获取默认设置
        
        Returns:
            包含所有默认字段值的字典
        """
        return {
            "id": "global",
            # 向量嵌入模型默认值
            "embedding_provider": "huggingface",
            "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_api_key": "",
            "embedding_base_url": "",
            # 大语言模型默认值
            "llm_provider": "deepseek",
            "llm_model_name": "deepseek-chat",
            "llm_api_key": "",
            "llm_base_url": "https://api.deepseek.com",
            "llm_temperature": "0.7",
            # 提示词默认值
            "chat_system_prompt": "你是一个专业的AI助手。请友好、准确地回答用户的问题。",
            "rag_system_prompt": "你是一个专业的AI助手。请基于文档内容回答问题。",
            "rag_query_prompt": "文档内容：\n{context}\n\n问题：{question}\n\n请基于文档内容回答问题。如果文档中没有相关信息，请明确说明。",
            # 检索设置默认值（与数据库默认值保持一致）
            "retrieval_mode": "vector",
            "vector_threshold": 0.2,
            "keyword_threshold": 0.2,
            "vector_weight": 0.5,
            "top_k": 5,
        }

    def get(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        获取设置
        
        Returns:
            (设置字典, 错误信息) - 成功时错误信息为 None
        """
        try:
            with session_scope() as session:
                settings = session.query(Settings).filter_by(id="global").first()
                
                if settings:
                    return settings.to_dict(), None
                else:
                    # 返回默认设置
                    return self._get_default_settings(), None
                    
        except Exception as e:
            logger.error(f"获取设置失败: {e}")
            return None, "获取设置失败"

    def update(self, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        更新设置
        
        Args:
            data: 要更新的设置数据
            
        Returns:
            (更新后的设置字典, 错误信息) - 成功时错误信息为 None
        """
        # 允许更新的字段
        allowed_fields = {
            "embedding_provider",
            "embedding_model_name",
            "embedding_api_key",
            "embedding_base_url",
            "llm_provider",
            "llm_model_name",
            "llm_api_key",
            "llm_base_url",
            "llm_temperature",
            "chat_system_prompt",
            "rag_system_prompt",
            "rag_query_prompt",
            "retrieval_mode",
            "vector_threshold",
            "keyword_threshold",
            "vector_weight",
            "top_k",
        }

        # 过滤掉不允许更新的字段
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            return None, "没有有效的更新字段"

        # 验证检索模式
        if "retrieval_mode" in update_data:
            if update_data["retrieval_mode"] not in ["vector", "keyword", "hybrid"]:
                return None, "无效的检索模式"

        # 验证数值范围
        if "vector_threshold" in update_data:
            try:
                val = float(update_data["vector_threshold"])
                if not (0 <= val <= 1):
                    return None, "向量检索阈值应在 0-1 之间"
            except (TypeError, ValueError):
                return None, "向量检索阈值格式错误"

        if "keyword_threshold" in update_data:
            try:
                val = float(update_data["keyword_threshold"])
                if not (0 <= val <= 1):
                    return None, "全文检索阈值应在 0-1 之间"
            except (TypeError, ValueError):
                return None, "全文检索阈值格式错误"

        if "vector_weight" in update_data:
            try:
                val = float(update_data["vector_weight"])
                if not (0 <= val <= 1):
                    return None, "向量检索权重应在 0-1 之间"
            except (TypeError, ValueError):
                return None, "向量检索权重格式错误"

        if "top_k" in update_data:
            try:
                val = int(update_data["top_k"])
                if not (1 <= val <= 50):
                    return None, "TopK 应在 1-50 之间"
            except (TypeError, ValueError):
                return None, "TopK 格式错误"

        if "llm_temperature" in update_data:
            try:
                val = float(update_data["llm_temperature"])
                if not (0 <= val <= 2):
                    return None, "温度应在 0-2 之间"
                # 转换为字符串存储（数据库字段是 String 类型）
                update_data["llm_temperature"] = str(val)
            except (TypeError, ValueError):
                return None, "温度格式错误"

        # 验证 embedding_model_name 不能为空（数据库 nullable=False）
        if "embedding_model_name" in update_data:
            if not update_data["embedding_model_name"]:
                return None, "向量嵌入模型名称不能为空"

        try:
            with session_scope() as session:
                # 查询现有设置
                settings = session.query(Settings).filter_by(id="global").first()
                
                if not settings:
                    # 如果不存在，创建新记录
                    settings = Settings(id="global")
                    # 先设置默认值
                    default_settings = self._get_default_settings()
                    for key, value in default_settings.items():
                        if hasattr(settings, key) and key != "id":
                            setattr(settings, key, value)
                    session.add(settings)
                
                # 更新字段
                for key, value in update_data.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                
                session.flush()
                result = settings.to_dict()
                
                logger.info("设置更新成功")
                return result, None

        except Exception as e:
            logger.error(f"更新设置失败: {e}")
            return None, "更新设置失败"


# 创建全局服务实例
settings_service = SettingsService()
