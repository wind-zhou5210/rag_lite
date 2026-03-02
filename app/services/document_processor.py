"""
文档处理服务

负责文档的异步处理任务调度
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.services.document_service import doc_service
from app.services.settings_service import settings_service
from app.services.storage import get_storage_provider
from app.services.parser import get_parser
from app.services.embedding.factory import get_embedding, get_embedding_dimension
from app.services.vector_store.factory import get_vector_store
from app.util.logger import get_logger
from app.util.db import session_scope
from app.models.document import Document, DocumentStatus
from app.models.knowledgebase import Knowledgebase

logger = get_logger(__name__)


class DocumentProcessor:
    """文档处理服务类

    负责调度文档处理任务，包括：
    - 文件解析
    - 文本分块
    - 向量化
    - 向量存储
    """

    def __init__(self, max_workers: int = 4):
        """
        初始化文档处理器

        Args:
            max_workers: 线程池最大工作线程数
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"文档处理器初始化完成，最大工作线程数: {max_workers}")

    def submit_process_task(self, kb_id: str, doc_id: str, user_id: str) -> tuple:
        """
        提交文档处理任务

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            tuple: (success, error_message)
        """
        try:
            # 更新文档状态为 processing
            result, error = doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.PROCESSING
            )
            if error:
                return False, error

            # 提交到线程池
            self.executor.submit(
                self._process_document,
                kb_id,
                doc_id,
                user_id
            )

            logger.info(f"文档处理任务已提交: kb_id={kb_id}, doc_id={doc_id}")
            return True, None

        except Exception as e:
            logger.error(f"提交处理任务失败: {e}")
            return False, "提交处理任务失败"

    def submit_reprocess_task(self, kb_id: str, doc_id: str, user_id: str) -> tuple:
        """
        提交文档重处理任务

        重处理时会先删除旧的向量数据，然后重新处理。

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            tuple: (success, error_message)
        """
        try:
            # 先删除旧的向量数据
            collection_name = f"kb_{kb_id}"
            vector_store = get_vector_store()
            vector_store.delete_by_doc_id(collection_name, doc_id)
            logger.info(f"已删除文档旧向量数据: doc_id={doc_id}")

            # 然后提交处理任务
            return self.submit_process_task(kb_id, doc_id, user_id)

        except Exception as e:
            logger.error(f"提交重处理任务失败: {e}")
            return False, "提交重处理任务失败"

    def _process_document(self, kb_id: str, doc_id: str, user_id: str):
        """
        处理文档的核心逻辑（在线程池中执行）

        处理流程：
        1. 获取文档和知识库信息
        2. 获取用户配置（Embedding）
        3. 获取文件本地路径
        4. 解析文件 → 获取文本
        5. 按 chunk_size/overlap 分块
        6. 获取 Embedding 实例
        7. 批量向量化文本块
        8. 确保 Collection 存在（不存在则创建）
        9. 插入向量（带 doc_id, kb_id 元数据）
        10. 更新文档状态 + chunk_count

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID
        """
        temp_file_path = None

        try:
            # 1. 获取文档和知识库信息
            with session_scope() as session:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                kb = session.query(Knowledgebase).filter(Knowledgebase.id == kb_id).first()

                if not doc or not kb:
                    raise Exception("文档或知识库不存在")

                file_path = doc.file_path
                file_type = doc.file_type
                chunk_size = kb.chunk_size
                chunk_overlap = kb.chunk_overlap

            # 2. 获取用户配置
            settings, _ = settings_service.get()
            if not settings:
                raise Exception("获取用户配置失败")

            # 3. 获取文件本地路径
            storage = get_storage_provider()
            local_file_path = storage.get_file_path(file_path)

            if local_file_path is None:
                # 如果不支持直接获取路径，需要下载到临时目录
                temp_file_path = self._download_to_temp(storage, file_path)
                local_file_path = temp_file_path

            if not local_file_path or not os.path.exists(local_file_path):
                raise Exception(f"文件不存在: {file_path}")

            # 4. 解析文件
            parser = get_parser(file_type)
            text_content, error = parser.parse(local_file_path)
            if error:
                raise Exception(f"文件解析失败: {error}")

            if not text_content or not text_content.strip():
                raise Exception("文件内容为空")

            # 5. 文本分块
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
            )
            chunks = text_splitter.split_text(text_content)
            logger.info(f"文档分块完成，共 {len(chunks)} 个块: doc_id={doc_id}")

            # 6. 获取 Embedding 实例
            embedding = get_embedding(settings)
            dimension = get_embedding_dimension(settings)

            # 7. 获取向量存储，确保 Collection 存在
            vector_store = get_vector_store()
            collection_name = f"kb_{kb_id}"

            # 7.1 先删除该文档的旧向量数据，防止重复
            vector_store.delete_by_doc_id(collection_name, doc_id)
            logger.info(f"已清理文档旧向量数据: doc_id={doc_id}")

            if not vector_store.collection_exists(collection_name):
                success, error = vector_store.create_collection(collection_name, dimension)
                if not success:
                    raise Exception(f"创建 Collection 失败: {error}")

            # 8. 批量向量化
            logger.debug(f"开始向量化: doc_id={doc_id}, chunks={len(chunks)}")
            embeddings = embedding.embed_documents(chunks)

            # 9. 插入向量存储
            metadata = {
                "doc_id": doc_id,
                "kb_id": kb_id,
            }
            success, error = vector_store.insert(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata
            )
            if not success:
                raise Exception(f"向量存储失败: {error}")

            # 10. 更新文档状态为 completed
            doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.COMPLETED,
                chunk_count=len(chunks),
                error_message=None
            )

            logger.info(f"文档处理完成: doc_id={doc_id}, chunks={len(chunks)}")

        except Exception as e:
            logger.error(f"文档处理失败: doc_id={doc_id}, error={e}")
            # 更新文档状态为 failed
            doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.FAILED,
                error_message=str(e)
            )

        finally:
            # 清理临时文件
            if temp_file_path:
                try:
                    os.remove(temp_file_path)
                    logger.debug(f"临时文件已清理: {temp_file_path}")
                except Exception:
                    pass

    def _download_to_temp(self, storage, object_key: str) -> Optional[str]:
        """
        下载文件到临时目录

        Args:
            storage: 存储提供者
            object_key: 文件标识

        Returns:
            Optional[str]: 临时文件路径
        """
        import tempfile
        import requests

        try:
            # 获取文件 URL
            url = storage.get_url(object_key)
            if not url:
                return None

            # 获取文件扩展名
            ext = os.path.splitext(object_key)[1] or '.tmp'

            # 下载到临时文件
            response = requests.get(url, timeout=300)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(mode='wb', suffix=ext, delete=False) as f:
                f.write(response.content)
                temp_path = f.name

            logger.debug(f"文件下载到临时目录: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return None

    def shutdown(self, wait: bool = True):
        """
        关闭线程池

        Args:
            wait: 是否等待任务完成
        """
        self.executor.shutdown(wait=wait)
        logger.info("文档处理器已关闭")


# 创建全局实例
document_processor = DocumentProcessor()
