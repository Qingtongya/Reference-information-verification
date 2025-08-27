from typing import List, Dict
import requests
import json
import re


class CitationValidator:
    def __init__(self, rag_builder):
        self.rag_builder = rag_builder

    def validate_with_rag(self, citations: List[Dict]) -> List[Dict]:
        """使用RAG验证引用的真实性"""
        validated_citations = []

        for citation in citations:
            citation_type = citation.get("type")
            title = citation.get("title")
            content = citation.get("content", "")

            # 使用RAG搜索相关文档
            query = f"{title} {content}"
            results = self.rag_builder.search(query, k=3)

            if results:
                # 找到相关文档，标记为已验证
                citation["validated"] = True
                citation["validation_result"] = "通过RAG验证找到相关文档"
                citation["rag_results"] = results
                citation["similarity_scores"] = [result["score"] for result in results]
            else:
                # 未找到相关文档，标记为未验证
                citation["validated"] = False
                citation["validation_result"] = "通过RAG验证未找到相关文档"

            validated_citations.append(citation)

        return validated_citations

    def llm_validate_citations(self, api_key: str, citations: List[Dict]) -> List[Dict]:
        """使用大模型验证引用的真实性"""
        # 准备提示词
        prompt = f"""
        请验证以下引用是否真实有效。对于每个引用，请提供验证结果和理由。

        引用列表：
        {json.dumps(citations, ensure_ascii=False)}

        请以JSON格式返回结果，包含一个数组，每个元素是一个验证结果对象，包含：
        - original_index: 原始引用在数组中的索引
        - is_valid: 是否有效
        - validation_reason: 验证理由
        - suggested_correction: 如果有误，建议的修正
        """

        try:
            # 调用硅基流动API
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "deepseek-ai/DeepSeek-R1",
                "max_tokens": 1024,
                "temperature": 0.3,
                "top_p": 0.8,
                "n": 1,
                "messages": [
                    {
                        "content": prompt,
                        "role": "user"
                    }
                ],
                "stream": False
            }

            # 配置会话
            session = requests.Session()
            if hasattr(self.rag_builder, 'use_proxy') and self.rag_builder.use_proxy and hasattr(self.rag_builder,
                                                                                                 'proxy_url'):
                session.proxies = {
                    "http": self.rag_builder.proxy_url,
                    "https": self.rag_builder.proxy_url,
                }
            else:
                session.trust_env = False  # 不信任环境变量中的代理设置

            response = session.post("https://api.siliconflow.cn/v1/chat/completions", json=payload, headers=headers,
                                    timeout=30)
            response.raise_for_status()
            result = response.json()
            response_text = result['choices'][0]['message']['content']

            # 从响应中提取JSON部分
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                validation_results = json.loads(json_match.group())

                # 将验证结果合并到引用中
                for i, citation in enumerate(citations):
                    if i < len(validation_results):
                        result = validation_results[i]
                        citation["llm_validated"] = result.get("is_valid", False)
                        citation["llm_validation_reason"] = result.get("validation_reason", "")
                        citation["llm_suggested_correction"] = result.get("suggested_correction", "")

                return citations
            else:
                # 如果模型没有返回标准JSON，返回原始引用
                return citations
        except Exception as e:
            print(f"大模型验证引用时出错: {str(e)}")
            return citations