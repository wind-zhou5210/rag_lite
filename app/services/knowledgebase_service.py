"""
知识库服务模块

提供知识库的创建、查询、更新、删除等业务逻辑
"""

from typing import Optional, Tuple, Dict, Any, List

from sqlalchemy.exc import IntegrityError

from app.models.knowledgebase import Knowledgebase
from app.util.db import session_scope
from app.util.logger import get_logger


logger = get_logger(__name__)


def _get_storage_provider():
    """延迟加载存储提供者，避免循环导入"""
    from app.services.storage import get_storage_provider
    return get_storage_provider()


class KnowledgebaseService:
    """知识库服务类"""

    def _convert_cover_url(self, kb_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 cover_image（object_key）转换为可访问的 URL
        
        Args:
            kb_dict: 知识库字典数据
        
        Returns:
            添加了 cover_image_url 字段的字典
        """
        if kb_dict.get('cover_image'):
            try:
                storage = _get_storage_provider()
                kb_dict['cover_image_url'] = storage.get_url(kb_dict['cover_image'])
            except Exception as e:
                logger.warning(f"获取封面图片 URL 失败: {e}")
                kb_dict['cover_image_url'] = None
        else:
            kb_dict['cover_image_url'] = None
        return kb_dict
    
    def _convert_cover_url_list(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量转换列表中的 cover_image URL
        
        Args:
            items: 知识库字典列表
        
        Returns:
            转换后的列表
        """
        return [self._convert_cover_url(item) for item in items]
    
    def _delete_cover_image(self, object_key: Optional[str]) -> None:
        """
        删除封面图片
        
        Args:
            object_key: 图片的 object_key
        """
        if not object_key:
            return
        
        try:
            storage = _get_storage_provider()
            success, error = storage.delete(object_key)
            if success:
                logger.info(f"封面图片删除成功: {object_key}")
            else:
                logger.warning(f"封面图片删除失败: {error}")
        except Exception as e:
            logger.warning(f"删除封面图片异常: {e}")

    def create(
        self,
        user_id: str,
        name: str,
        chunk_size: int,
        chunk_overlap: int,
        description: Optional[str] = None,
        cover_image: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        创建知识库

        Args:
            user_id: 用户 ID
            name: 知识库名称
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
            description: 描述（可选）
            cover_image: 封面图片路径（可选，暂不处理）

        Returns:
            (知识库信息字典, 错误信息) - 成功时错误信息为 None
        """
        kb = Knowledgebase(
            user_id=user_id,
            name=name,
            description=description,
            cover_image=cover_image,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        try:
            with session_scope() as session:
                session.add(kb)
                session.flush()  # 获取生成的 ID
                # 在 session 内部转换为字典，避免 detached 问题
                kb_dict = kb.to_dict()
                # 转换封面图片 URL
                kb_dict = self._convert_cover_url(kb_dict)
                logger.info(f"知识库 {name} 创建成功，ID: {kb.id}")
                return kb_dict, None

        except IntegrityError as e:
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "name" in error_msg.lower() or "duplicate" in error_msg.lower():
                logger.warning(f"知识库名称 {name} 已存在")
                return None, "知识库名称已存在"
            else:
                logger.error(f"创建知识库失败: {e}")
                return None, "创建知识库失败"

        except Exception as e:
            logger.error(f"创建知识库异常: {e}")
            return None, "服务器内部错误"

    def get_by_id(
        self,
        kb_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        根据 ID 查询知识库

        Args:
            kb_id: 知识库 ID
            user_id: 用户 ID（用于权限验证，传入时只返回该用户的知识库）

        Returns:
            (知识库信息字典, 错误信息)
        """
        try:
            with session_scope() as session:
                query = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id
                )
                # 如果传入 user_id，则加入用户过滤（权限验证）
                if user_id:
                    query = query.filter(Knowledgebase.user_id == user_id)

                kb = query.first()

                if not kb:
                    return None, "知识库不存在或无权访问"

                kb_dict = kb.to_dict()
                # 转换封面图片 URL
                kb_dict = self._convert_cover_url(kb_dict)
                return kb_dict, None

        except Exception as e:
            logger.error(f"查询知识库失败: {e}")
            return None, "服务器内部错误"

    def get_list(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        分页查询用户的知识库列表

        Args:
            user_id: 用户 ID（用户隔离）
            page: 页码，从 1 开始
            page_size: 每页数量

        Returns:
            (分页数据字典, 错误信息)
        """
        try:
            with session_scope() as session:
                # 构建查询，只查询当前用户的知识库
                query = session.query(Knowledgebase).filter(
                    Knowledgebase.user_id == user_id
                )

                # 获取总数
                total = query.count()

                # 分页查询，按创建时间倒序
                offset = (page - 1) * page_size
                kbs = query.order_by(Knowledgebase.created_at.desc())\
                    .offset(offset)\
                    .limit(page_size)\
                    .all()

                # 转换为字典列表
                items = [kb.to_dict() for kb in kbs]
                # 转换封面图片 URL
                items = self._convert_cover_url_list(items)

                result = {
                    "items": items,
                    "page": page,
                    "page_size": page_size,
                    "total": total
                }

                return result, None

        except Exception as e:
            logger.error(f"查询知识库列表失败: {e}")
            return None, "服务器内部错误"

    def update(
        self,
        kb_id: str,
        user_id: str,
        **update_data
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        更新知识库

        Args:
            kb_id: 知识库 ID
            user_id: 用户 ID（用于权限验证）
            **update_data: 要更新的字段（name, description, chunk_size, chunk_overlap, cover_image）

        Returns:
            (更新后的知识库信息, 错误信息)
        """
        # 允许更新的字段
        allowed_fields = {"name", "description", "chunk_size", "chunk_overlap", "cover_image"}
        # 过滤掉不允许更新的字段
        update_data = {k: v for k, v in update_data.items() if k in allowed_fields}

        if not update_data:
            return None, "没有有效的更新字段"

        # 用于记录需要在事务成功后删除的图片
        image_to_delete = None
        kb_dict = None

        try:
            with session_scope() as session:
                # 查询并验证权限
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return None, "知识库不存在或无权操作"

                # 校验 chunk_overlap < chunk_size（结合数据库现有值）
                new_chunk_size = update_data.get("chunk_size", kb.chunk_size)
                new_chunk_overlap = update_data.get("chunk_overlap", kb.chunk_overlap)
                if new_chunk_overlap >= new_chunk_size:
                    return None, "分块重叠大小不能大于等于分块大小"

                # 检查是否更换了封面图片
                old_cover_image = kb.cover_image
                new_cover_image = update_data.get("cover_image")
                cover_image_changed = (
                    "cover_image" in update_data and 
                    old_cover_image and 
                    new_cover_image != old_cover_image
                )

                # 更新字段
                for key, value in update_data.items():
                    setattr(kb, key, value)

                session.flush()
                kb_dict = kb.to_dict()
                # 转换封面图片 URL
                kb_dict = self._convert_cover_url(kb_dict)

                # 如果更换了封面，记录待删除的旧图片
                if cover_image_changed:
                    image_to_delete = old_cover_image

                logger.info(f"知识库 {kb_id} 更新成功")
            
            # 事务提交成功后，删除旧图片（在 session_scope 外部执行）
            if image_to_delete:
                self._delete_cover_image(image_to_delete)
            
            return kb_dict, None

        except IntegrityError as e:
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "name" in error_msg.lower() or "duplicate" in error_msg.lower():
                logger.warning(f"知识库名称已存在")
                return None, "知识库名称已存在"
            else:
                logger.error(f"更新知识库失败: {e}")
                return None, "更新知识库失败"

        except Exception as e:
            logger.error(f"更新知识库异常: {e}")
            return None, "服务器内部错误"

    def delete(
        self,
        kb_id: str,
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        删除知识库

        Args:
            kb_id: 知识库 ID
            user_id: 用户 ID（用于权限验证）

        Returns:
            (是否成功, 错误信息)
        """
        # 用于记录需要在事务成功后删除的图片
        image_to_delete = None
        kb_name = None
        
        try:
            with session_scope() as session:
                # 查询并验证权限
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return False, "知识库不存在或无权操作"

                kb_name = kb.name
                image_to_delete = kb.cover_image
                session.delete(kb)

                logger.info(f"知识库 {kb_name}({kb_id}) 删除成功")
            
            # 事务提交成功后，删除关联的封面图片（在 session_scope 外部执行）
            if image_to_delete:
                self._delete_cover_image(image_to_delete)
            
            return True, None

        except Exception as e:
            logger.error(f"删除知识库异常: {e}")
            return False, "服务器内部错误"


# 创建全局服务实例
kb_service = KnowledgebaseService()
