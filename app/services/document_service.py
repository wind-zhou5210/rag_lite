"""
文档服务模块

提供文档的创建、查询、更新、删除等业务逻辑
"""

from typing import Optional, Tuple, Dict, Any, List

from sqlalchemy.exc import IntegrityError

from app.models.document import Document, DocumentStatus
from app.models.knowledgebase import Knowledgebase
from app.util.db import session_scope
from app.util.logger import get_logger


logger = get_logger(__name__)


def _get_storage_provider():
    """延迟加载存储提供者，避免循环导入"""
    from app.services.storage import get_storage_provider
    return get_storage_provider()


class DocumentService:
    """文档服务类"""

    def create(
        self,
        kb_id: str,
        user_id: str,
        name: str,
        file_path: str,
        file_type: str,
        file_size: int
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        创建文档记录

        Args:
            kb_id: 知识库 ID
            user_id: 用户 ID（用于权限验证）
            name: 文档名称
            file_path: 文件存储路径（object_key）
            file_type: 文件类型
            file_size: 文件大小（字节）

        Returns:
            (文档信息字典, 错误信息)
        """
        try:
            with session_scope() as session:
                # 验证知识库存在且属于当前用户
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return None, "知识库不存在或无权访问"

                # 创建文档
                doc = Document(
                    kb_id=kb_id,
                    name=name,
                    file_path=file_path,
                    file_type=file_type,
                    file_size=file_size,
                    status=DocumentStatus.PENDING
                )

                session.add(doc)
                session.flush()

                doc_dict = doc.to_dict()
                logger.info(f"文档 {name} 创建成功，ID: {doc.id}")
                return doc_dict, None

        except Exception as e:
            logger.error(f"创建文档异常: {e}")
            return None, "服务器内部错误"

    def get_list(
        self,
        kb_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        分页获取知识库的文档列表

        Args:
            kb_id: 知识库 ID
            user_id: 用户 ID（用于权限验证）
            page: 页码
            page_size: 每页数量

        Returns:
            (分页数据字典, 错误信息)
        """
        try:
            with session_scope() as session:
                # 验证知识库存在且属于当前用户
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return None, "知识库不存在或无权访问"

                # 查询文档列表
                query = session.query(Document).filter(
                    Document.kb_id == kb_id
                )

                # 获取总数
                total = query.count()

                # 分页查询，按创建时间倒序
                offset = (page - 1) * page_size
                docs = query.order_by(Document.created_at.desc())\
                    .offset(offset)\
                    .limit(page_size)\
                    .all()

                # 转换为字典列表
                items = [doc.to_dict() for doc in docs]

                result = {
                    "items": items,
                    "page": page,
                    "page_size": page_size,
                    "total": total
                }

                return result, None

        except Exception as e:
            logger.error(f"查询文档列表失败: {e}")
            return None, "服务器内部错误"

    def get_by_id(
        self,
        kb_id: str,
        doc_id: str,
        user_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        获取单个文档详情

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            (文档信息字典, 错误信息)
        """
        try:
            with session_scope() as session:
                # 验证知识库存在且属于当前用户
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return None, "知识库不存在或无权访问"

                # 查询文档
                doc = session.query(Document).filter(
                    Document.id == doc_id,
                    Document.kb_id == kb_id
                ).first()

                if not doc:
                    return None, "文档不存在"

                return doc.to_dict(), None

        except Exception as e:
            logger.error(f"查询文档失败: {e}")
            return None, "服务器内部错误"

    def delete(
        self,
        kb_id: str,
        doc_id: str,
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        删除文档

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            (是否成功, 错误信息)
        """
        file_to_delete = None
        doc_name = None

        try:
            with session_scope() as session:
                # 验证知识库存在且属于当前用户
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return False, "知识库不存在或无权访问"

                # 查询文档
                doc = session.query(Document).filter(
                    Document.id == doc_id,
                    Document.kb_id == kb_id
                ).first()

                if not doc:
                    return False, "文档不存在"

                # 禁止删除正在处理中的文档
                if doc.status == DocumentStatus.PROCESSING:
                    return False, "文档正在处理中，无法删除"

                doc_name = doc.name
                file_to_delete = doc.file_path

                session.delete(doc)
                logger.info(f"文档 {doc_name}({doc_id}) 删除成功")

            # 事务成功后删除存储文件
            if file_to_delete:
                self._delete_file(file_to_delete)

            return True, None

        except Exception as e:
            logger.error(f"删除文档异常: {e}")
            return False, "服务器内部错误"

    def update_status(
        self,
        kb_id: str,
        doc_id: str,
        user_id: str,
        status: str,
        chunk_count: int = None,
        error_message: str = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        更新文档状态

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID
            status: 新状态
            chunk_count: 分块数量（可选）
            error_message: 错误信息（可选）

        Returns:
            (更新后的文档信息, 错误信息)
        """
        if not DocumentStatus.is_valid(status):
            return None, f"无效的状态值: {status}"

        try:
            with session_scope() as session:
                # 验证知识库存在且属于当前用户
                kb = session.query(Knowledgebase).filter(
                    Knowledgebase.id == kb_id,
                    Knowledgebase.user_id == user_id
                ).first()

                if not kb:
                    return None, "知识库不存在或无权访问"

                # 查询文档
                doc = session.query(Document).filter(
                    Document.id == doc_id,
                    Document.kb_id == kb_id
                ).first()

                if not doc:
                    return None, "文档不存在"

                # 更新状态
                doc.status = status
                if chunk_count is not None:
                    doc.chunk_count = chunk_count
                if error_message is not None:
                    doc.error_message = error_message

                session.flush()
                doc_dict = doc.to_dict()
                logger.info(f"文档 {doc_id} 状态更新为: {status}")
                return doc_dict, None

        except Exception as e:
            logger.error(f"更新文档状态异常: {e}")
            return None, "服务器内部错误"

    def _delete_file(self, object_key: str) -> None:
        """
        删除存储文件

        Args:
            object_key: 文件的 object_key
        """
        if not object_key:
            return

        try:
            storage = _get_storage_provider()
            success, error = storage.delete(object_key)
            if success:
                logger.info(f"文档文件删除成功: {object_key}")
            else:
                logger.warning(f"文档文件删除失败: {error}")
        except Exception as e:
            logger.warning(f"删除文档文件异常: {e}")


# 创建全局服务实例
doc_service = DocumentService()
