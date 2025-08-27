import requests
import numpy as np
import faiss
import json
import os
import re
from typing import List, Dict, Any
import PyPDF2
import docx
import spacy
from spacy.lang.zh import Chinese
from datetime import datetime


class RAGBuilder:
    def __init__(self, api_key: str,
                 embedding_model: str = "Qwen/Qwen3-Embedding-8B",
                 use_proxy=False, proxy_url=None):
        self.api_key = api_key
        self.embedding_model = embedding_model
        self.embedding_url = "https://api.siliconflow.cn/v1/embeddings"
        self.index = None
        self.documents = []  # 存储文档内容
        self.document_metadata = []  # 存储文档元数据
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url

        # 加载spacy中文模型
        try:
            self.nlp = spacy.load("zh_core_web_sm")
        except OSError:
            # 如果模型不存在，创建一个基础的中文处理器
            self.nlp = Chinese()
            self.nlp.add_pipe("sentencizer")

    def extract_text_from_file(self, file_path: str) -> str:
        """从文件中提取文本"""
        if file_path.lower().endswith('.pdf'):
            return self.extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return self.extract_text_from_docx(file_path)
        elif file_path.lower().endswith('.txt'):
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path}")

    def extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF提取文本"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            raise Exception(f"读取PDF文档失败: {str(e)}")

    def extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档提取文本"""
        try:
            doc = docx.Document(file_path)
            full_text = []
            for paragraph in doc.paragraphs:
                full_text.append(paragraph.text)
            return '\n'.join(full_text)
        except Exception as e:
            raise Exception(f"读取Word文档失败: {str(e)}")

    def extract_text_from_txt(self, file_path: str) -> str:
        """从文本文件提取文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"读取文本文件失败: {str(e)}")

    def split_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """使用spacy将文本分割成块"""
        # 处理文本
        doc = self.nlp(text)

        # 提取句子
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # 如果当前块加上新句子不会超过大小限制
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                # 保存当前块并开始新块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())

        # 如果没有句子被识别，使用简单的分割方法作为后备
        if not chunks:
            # 使用正则表达式分割句子
            sentences = re.split(r'(?<=[。！？!?])', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "

            if current_chunk:
                chunks.append(current_chunk.strip())

        return chunks

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """获取文本的嵌入向量"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.embedding_model,
            "input": texts,
            "encoding_format": "float"
        }

        try:
            # 配置会话
            session = requests.Session()
            if self.use_proxy and self.proxy_url:
                session.proxies = {
                    "http": self.proxy_url,
                    "https": self.proxy_url,
                }
            else:
                session.trust_env = False  # 不信任环境变量中的代理设置

            response = session.post(self.embedding_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 提取嵌入向量
            embeddings = [item['embedding'] for item in result['data']]
            return np.array(embeddings).astype('float32')
        except Exception as e:
            raise Exception(f"获取嵌入向量失败: {str(e)}")

    def build_index(self, documents: List[str], metadata: List[Dict] = None):
        """构建FAISS索引"""
        if not documents:
            raise ValueError("文档列表不能为空")

        # 获取文档的嵌入向量
        embeddings = self.get_embeddings(documents)

        # 创建FAISS索引
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)

        # 存储文档和元数据
        self.documents = documents
        self.document_metadata = metadata if metadata else [{} for _ in documents]

    def add_document(self, file_path: str, metadata: Dict = None) -> Dict:
        """添加单个文档到索引"""
        # 提取文本
        text = self.extract_text_from_file(file_path)

        # 分割文本
        chunks = self.split_text(text)

        # 获取嵌入向量
        embeddings = self.get_embeddings(chunks)

        # 添加到索引
        if self.index is None:
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dimension)

        self.index.add(embeddings)

        # 添加到文档列表
        for chunk in chunks:
            self.documents.append(chunk)
            self.document_metadata.append({
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "added_date": datetime.now().isoformat(),
                **(metadata if metadata else {})
            })

        return {
            "file_path": file_path,
            "chunk_count": len(chunks),
            "total_chunks": len(self.documents)
        }

    def add_documents_from_folder(self, folder_path: str, file_extensions: List[str] = None) -> List[Dict]:
        """从文件夹添加多个文档"""
        if file_extensions is None:
            file_extensions = ['.pdf', '.docx', '.txt']

        results = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in file_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        result = self.add_document(file_path)
                        result["status"] = "success"
                        results.append(result)
                        print(f"已添加文档: {file}")
                    except Exception as e:
                        results.append({
                            "file_path": file_path,
                            "status": "error",
                            "error": str(e)
                        })
                        print(f"添加文档失败 {file}: {str(e)}")

        return results

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """搜索最相关的文档片段"""
        if self.index is None or len(self.documents) == 0:
            return []

        # 获取查询的嵌入向量
        query_embedding = self.get_embeddings([query])

        # 搜索最相似的k个文档
        distances, indices = self.index.search(query_embedding, k)

        # 构建结果
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                results.append({
                    "document": self.documents[idx],
                    "metadata": self.document_metadata[idx],
                    "score": float(distances[0][i])
                })

        return results

    def save_index(self, file_path: str) -> bool:
        """保存FAISS索引和文档数据"""
        if self.index is None:
            return False

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            # 保存FAISS索引
            faiss.write_index(self.index, f"{file_path}.index")

            # 保存文档数据
            data = {
                "documents": self.documents,
                "metadata": self.document_metadata,
                "saved_date": datetime.now().isoformat(),
                "embedding_model": self.embedding_model
            }

            with open(f"{file_path}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"保存索引失败: {str(e)}")
            return False

    def load_index(self, file_path: str) -> bool:
        """加载FAISS索引和文档数据"""
        try:
            # 加载FAISS索引
            self.index = faiss.read_index(f"{file_path}.index")

            # 加载文档数据
            with open(f"{file_path}.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.documents = data["documents"]
                self.document_metadata = data["metadata"]

            return True
        except Exception as e:
            print(f"加载索引失败: {str(e)}")
            return False

    def get_index_status(self) -> Dict:
        """获取索引状态"""
        if self.index is None:
            return {
                "status": "未初始化",
                "document_count": 0,
                "file_count": 0,
                "dimension": 0
            }

        # 统计不同文件的文档数量
        file_stats = {}
        for meta in self.document_metadata:
            file_path = meta.get("file_path", "未知")
            if file_path not in file_stats:
                file_stats[file_path] = 0
            file_stats[file_path] += 1

        return {
            "status": "已初始化",
            "document_count": len(self.documents),
            "file_count": len(file_stats),
            "dimension": self.index.d if hasattr(self.index, 'd') else 0,
            "file_stats": file_stats
        }

    def clear_index(self) -> bool:
        """清空索引"""
        self.index = None
        self.documents = []
        self.document_metadata = []
        return True

    def is_index_loaded(self) -> bool:
        """检查索引是否已加载"""
        return self.index is not None and len(self.documents) > 0